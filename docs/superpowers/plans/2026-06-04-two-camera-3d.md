# Two-Camera 3D Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Triangulate the two synced camera views into a metric 3D skeleton and compute the body-rotation metrics 2D can't (shoulder/hip turn, X-factor + stretch, un-foreshortened side-bend), so live swings compare to the full `golftec_reference.json`.

**Architecture:** New `vision/threed/` subpackage (types → pluggable calibration → triangulation) feeds a new `pose_3d_frame` store table. New `metrics/defs/rotation_3d.py` + `sidebend_3d.py` read a `MetricContext.pose_3d` accessor and emit metrics with `method="triangulated_3d"` (same names as the 2D ones, plus new `x_factor_deg`/`x_factor_stretch_deg`). The 2D pipeline is untouched and stays the fallback. Validated against `smooth_swing.mov` with an approximate calibration; production accuracy comes from a checkerboard calibration captured once the bay exists.

**Tech Stack:** Python 3.12, NumPy, OpenCV (`cv2.triangulatePoints`, `cv2.stereoCalibrate`), MediaPipe (existing per-view 2D pose), sqlite (existing store), pytest.

**Spec:** `docs/superpowers/specs/2026-06-04-two-camera-3d-design.md`

> **DEFERRED BUILD.** Execute once the GarageTEC bay rig is set up. Tasks 1–10 are fully validatable *now* against `smooth_swing.mov` with the approximate calibration. Task 11 (`CheckerboardCalibration`) needs the physical bay calibration capture — do it last.

---

## File Structure

| File | Responsibility | Tasks |
|---|---|---|
| `store/models.py` | add `Landmark3D` dataclass | 1 |
| `store/schema.sql` | add `pose_3d_frame` table | 1 |
| `store/repo.py` | `save/get/clear_pose_3d_frames` + JSON helpers | 1 |
| `vision/threed/__init__.py` | package marker | 2 |
| `vision/threed/types.py` | `Pose3DTimeline` | 2 |
| `vision/threed/calibration.py` | `Calibration` base + `AssumedGeometryCalibration` (+ `CheckerboardCalibration`, Task 11) | 3, 11 |
| `vision/threed/reconstruct.py` | `triangulate_point`, `reconstruct(...)` | 4 |
| `metrics/geometry3d.py` | 3D angle helpers (signed angle about axis, project-to-plane, turn-vs-address) | 5 |
| `metrics/context.py` | add `pose_3d` + `pose_3d_at(kind)` to `MetricContext` | 6 |
| `metrics/defs/rotation_3d.py` | `shoulder_turn_deg`, `hip_turn_deg`, `x_factor_deg`, `x_factor_stretch_deg` | 7 |
| `metrics/defs/sidebend_3d.py` | 3D `shoulder_tilt_deg`/`hip_tilt_deg` @ top/impact | 8 |
| `metrics/defs/__init__.py` | import the two new defs modules | 7, 8 |
| `vision/pipeline.py` | optional 3D reconstruct + persist | 9 |
| `vision/constants.py` | 3D config constants | 9 |
| `coach/golftec.py` | load `golftec_reference.json` + `compare_golftec(...)` respecting 3D availability | 10 |
| `coach/tests/`, `store/tests/`, `metrics/tests/`, `vision/tests/` | tests per task | all |

---

## Task 1: `pose_3d_frame` store table + `Landmark3D` model + repo fns

**Files:**
- Modify: `store/models.py` (add `Landmark3D`)
- Modify: `store/schema.sql` (add table)
- Modify: `store/repo.py` (add helpers + 3 fns)
- Test: `store/tests/test_pose_3d.py`

- [ ] **Step 1: Write the failing test**

```python
# store/tests/test_pose_3d.py
# (the `db` fixture is provided by store/tests/conftest.py -> in-memory init_db)
from store import repo
from store.models import Landmark3D


def _swing(db):
    pid = repo.get_or_create_player(db, "T", 70.0, "R").id
    sid = repo.create_session(db, pid).id
    return repo.add_swing(db, sid, pid, "v.MOV").id


def test_save_get_clear_pose_3d_frames(db):
    swing_id = _swing(db)
    frames = {
        10: [Landmark3D("left_shoulder", 0.2, 1.4, 0.0, 0.99),
             Landmark3D("right_shoulder", -0.2, 1.4, 0.0, 0.98)],
        11: [Landmark3D("left_shoulder", 0.21, 1.4, 0.02, 0.97)],
    }
    n = repo.save_pose_3d_frames(db, swing_id, frames)
    assert n == 2
    got = repo.get_pose_3d_frames(db, swing_id)
    assert set(got.keys()) == {10, 11}
    lm = got[10][0]
    assert lm.name == "left_shoulder"
    assert abs(lm.x - 0.2) < 1e-9 and abs(lm.confidence - 0.99) < 1e-9
    assert repo.clear_pose_3d_frames(db, swing_id) == 2
    assert repo.get_pose_3d_frames(db, swing_id) == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest store/tests/test_pose_3d.py -v`
Expected: FAIL — `cannot import name 'Landmark3D'`.

- [ ] **Step 3: Add the `Landmark3D` model**

In `store/models.py`, after the `Landmark` dataclass (around line 69), add:

```python
@dataclass
class Landmark3D:
    name: str
    x: float          # metric meters, world frame
    y: float
    z: float
    confidence: float
```

- [ ] **Step 4: Add the table to `store/schema.sql`**

After the `pose_frame` table block, add:

```sql
CREATE TABLE IF NOT EXISTS pose_3d_frame (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  frame_index INTEGER NOT NULL,
  landmarks_json TEXT NOT NULL,
  UNIQUE(swing_id, frame_index)
);
```

(The schema is applied with `CREATE TABLE IF NOT EXISTS` on every `init_db`, so no migration is needed — existing DBs gain the table on next open.)

- [ ] **Step 5: Add repo helpers + functions**

In `store/repo.py`, near `_landmarks_to_json` / `_landmarks_from_json` (around line 260), add the 3D variants, and import `Landmark3D`:

```python
# add to the existing models import at top of repo.py:
from store.models import Landmark3D   # (extend the existing `from store.models import ...`)


def _landmarks3d_to_json(landmarks):
    return json.dumps([[lm.name, lm.x, lm.y, lm.z, lm.confidence]
                       for lm in landmarks])


def _landmarks3d_from_json(text):
    return [Landmark3D(n, x, y, z, c) for (n, x, y, z, c) in json.loads(text)]


def save_pose_3d_frames(conn, swing_id, frames_by_index):
    """frames_by_index: {frame_index: [Landmark3D]}."""
    rows = [(swing_id, idx, _landmarks3d_to_json(lms))
            for idx, lms in frames_by_index.items()]
    conn.executemany(
        "INSERT OR REPLACE INTO pose_3d_frame(swing_id, frame_index, "
        "landmarks_json) VALUES (?,?,?)", rows)
    conn.commit()
    return len(rows)


def get_pose_3d_frames(conn, swing_id):
    """Return {frame_index: [Landmark3D]} for the swing (empty dict if none)."""
    rows = conn.execute(
        "SELECT frame_index, landmarks_json FROM pose_3d_frame "
        "WHERE swing_id=? ORDER BY frame_index", (swing_id,)).fetchall()
    return {r["frame_index"]: _landmarks3d_from_json(r["landmarks_json"])
            for r in rows}


def clear_pose_3d_frames(conn, swing_id):
    cur = conn.execute("DELETE FROM pose_3d_frame WHERE swing_id=?", (swing_id,))
    conn.commit()
    return cur.rowcount
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest store/tests/test_pose_3d.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add store/models.py store/schema.sql store/repo.py store/tests/test_pose_3d.py
git commit -m "feat(store): pose_3d_frame table + Landmark3D + repo fns"
```

---

## Task 2: `vision/threed` package + `Pose3DTimeline`

**Files:**
- Create: `vision/threed/__init__.py`
- Create: `vision/threed/types.py`
- Test: `vision/tests/test_threed_types.py`

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_threed_types.py
from vision.threed.types import Pose3DTimeline
from store.models import Landmark3D


def test_pose3d_timeline_holds_frames():
    tl = Pose3DTimeline()
    tl.times_s.append(0.0)
    tl.frames.append([Landmark3D("nose", 0.0, 1.6, 0.1, 0.9)])
    tl.times_s.append(0.033)
    tl.frames.append(None)            # a dropped frame
    assert len(tl) == 2
    assert tl.frames[1] is None
    assert tl.frames[0][0].name == "nose"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest vision/tests/test_threed_types.py -v`
Expected: FAIL — `ModuleNotFoundError: vision.threed`.

- [ ] **Step 3: Create the package + types**

```python
# vision/threed/__init__.py
"""Two-camera 3D reconstruction: calibration -> triangulation -> 3D timeline."""
```

```python
# vision/threed/types.py
from dataclasses import dataclass, field
from typing import List, Optional

from store.models import Landmark3D


@dataclass
class Pose3DTimeline:
    """Parallel lists over composite frames. frames[i] = list[Landmark3D] in
    metric world coords, or None if that frame could not be reconstructed."""
    times_s: List[float] = field(default_factory=list)
    frames: List[Optional[List[Landmark3D]]] = field(default_factory=list)

    def __len__(self):
        return len(self.frames)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest vision/tests/test_threed_types.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add vision/threed/__init__.py vision/threed/types.py vision/tests/test_threed_types.py
git commit -m "feat(vision): vision/threed package + Pose3DTimeline"
```

---

## Task 3: `Calibration` interface + `AssumedGeometryCalibration`

**Files:**
- Create: `vision/threed/calibration.py`
- Test: `vision/tests/test_calibration.py`

**Context:** A `Calibration` yields two 3×4 projection matrices `P = K[R|t]` (world→image) and a world frame. The assumed provider places the **face-on** camera looking along world −Z (subject at origin facing +Z toward the camera) and the **down-line** camera rotated 90° about vertical (world +Y up), looking along world −X (down the target line, +X = toward target). Metric scale is set by anthropometry (`shoulder_width_m ≈ 0.24 × height_in × 0.0254`). World axes: X=target line, Y=up, Z=depth toward face-on camera.

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_calibration.py
import numpy as np
from vision.threed.calibration import AssumedGeometryCalibration


def test_projection_matrices_shape_and_world_frame():
    cal = AssumedGeometryCalibration(image_width=960, image_height=1080,
                                     height_in=70.0)
    P_fo, P_dl = cal.projection_matrices()
    assert P_fo.shape == (3, 4) and P_dl.shape == (3, 4)
    wf = cal.world_frame()
    assert np.allclose(wf["up"], [0, 1, 0])
    assert np.allclose(wf["target_line"], [1, 0, 0])


def test_assumed_geometry_projects_origin_near_image_center():
    cal = AssumedGeometryCalibration(image_width=960, image_height=1080,
                                     height_in=70.0)
    P_fo, _ = cal.projection_matrices()
    X = np.array([0.0, 0.0, 0.0, 1.0])          # world origin (subject center)
    uvw = P_fo @ X
    u, v = uvw[0] / uvw[2], uvw[1] / uvw[2]
    assert abs(u - 480) < 1.0 and abs(v - 540) < 1.0   # ~ image center
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest vision/tests/test_calibration.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the interface + assumed provider**

```python
# vision/threed/calibration.py
"""Pluggable camera calibration for triangulation.

Each Calibration yields two 3x4 projection matrices P = K[R|t] (world->image,
pixels) and a world frame {origin, up, target_line, depth}. AssumedGeometry is
an approximate provider for uncalibrated ~90-degree rigs (dev / smooth_swing.mov);
CheckerboardCalibration (Task 11) loads a real OpenCV stereo calibration.
"""
from typing import Dict, Tuple

import numpy as np

VIEW_FACE_ON = "face_on"
VIEW_DOWN_LINE = "down_line"
SHOULDER_HEIGHT_RATIO = 0.24
IN_TO_M = 0.0254


class Calibration:
    """Interface: projection_matrices() -> (P_face_on, P_down_line);
    world_frame() -> {origin, up, target_line, depth}; confidence tag."""
    confidence = "unknown"

    def projection_matrices(self) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def world_frame(self) -> Dict[str, object]:
        raise NotImplementedError


def _intrinsics(image_width, image_height, focal_px):
    cx, cy = image_width / 2.0, image_height / 2.0
    return np.array([[focal_px, 0, cx],
                     [0, focal_px, cy],
                     [0, 0, 1]], dtype=float)


def _projection(K, R, t):
    """P = K [R | t], where [R|t] maps world points into the camera frame."""
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


class AssumedGeometryCalibration(Calibration):
    """Orthogonal ~90-degree rig, no calibration target. APPROXIMATE."""
    confidence = "medium"

    def __init__(self, image_width, image_height, height_in,
                 focal_px=None, camera_distance_m=4.0):
        self.image_width = image_width
        self.image_height = image_height
        # default focal ~ image width => ~53 deg horizontal FOV (typical).
        self.focal_px = float(focal_px or image_width)
        self.height_in = height_in
        self.d = camera_distance_m
        # metric scale carried for downstream sanity (subject shoulder width).
        self.shoulder_width_m = SHOULDER_HEIGHT_RATIO * height_in * IN_TO_M

    def projection_matrices(self):
        K = _intrinsics(self.image_width, self.image_height, self.focal_px)
        # Face-on camera on +Z, looking toward origin (-Z). Camera axes:
        # x_cam = world +X (right), y_cam = world -Y (image y grows down),
        # z_cam = world -Z (viewing dir points from camera toward subject).
        R_fo = np.array([[1, 0, 0],
                         [0, -1, 0],
                         [0, 0, -1]], dtype=float)
        t_fo = np.array([0, 0, self.d], dtype=float)   # see note below
        # Down-line camera on +X, looking toward origin (-X) (rotate 90 about Y).
        R_dl = np.array([[0, 0, 1],
                         [0, -1, 0],
                         [-1, 0, 0]], dtype=float)
        t_dl = np.array([0, 0, self.d], dtype=float)
        return _projection(K, R_fo, t_fo), _projection(K, R_dl, t_dl)

    def world_frame(self):
        return {"origin": np.array([0.0, 0.0, 0.0]),
                "up": np.array([0.0, 1.0, 0.0]),
                "target_line": np.array([1.0, 0.0, 0.0]),
                "depth": np.array([0.0, 0.0, 1.0])}
```

> Note on `t`: `[R|t]` maps a world point `Xw` to camera coords `Xc = R·Xw + t`. With `R_fo` above and the camera sitting at world `+Z·d`, the world origin maps to `Xc = (0,0,d)` (in front of the camera at depth `d`), projecting to the image center — which the test asserts. The down-line `R_dl,t_dl` are constructed analogously so the origin also lands at camera depth `d`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest vision/tests/test_calibration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add vision/threed/calibration.py vision/tests/test_calibration.py
git commit -m "feat(vision/threed): Calibration interface + AssumedGeometry provider"
```

---

## Task 4: Triangulation core (`reconstruct`) + synthetic closed-loop test

**Files:**
- Create: `vision/threed/reconstruct.py`
- Test: `vision/tests/test_reconstruct.py`

**Context:** This is the correctness keystone. The synthetic test builds known 3D points, projects them with two known `P` matrices, then triangulates and asserts recovery — independent of any video or calibration accuracy. `reconstruct` consumes the two per-view `PoseTimeline`s (from `vision/types.py`, frames are `list[Landmark]|None` with pixel `.x/.y` + `.visibility`) and the calibration.

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_reconstruct.py
import numpy as np
from vision.threed.reconstruct import triangulate_point, reconstruct
from vision.threed.calibration import AssumedGeometryCalibration
from vision.types import PoseTimeline
from store.models import Landmark


def _project(P, X):
    uvw = P @ np.array([X[0], X[1], X[2], 1.0])
    return uvw[0] / uvw[2], uvw[1] / uvw[2]


def test_triangulate_recovers_known_point():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    X_true = np.array([0.18, 1.40, 0.05])           # a shoulder-ish point
    pt1, pt2 = _project(P1, X_true), _project(P2, X_true)
    X_rec = triangulate_point(P1, P2, pt1, pt2)
    assert np.allclose(X_rec, X_true, atol=1e-6)


def test_reconstruct_builds_timeline_with_world_points():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    X = {"left_shoulder": np.array([0.18, 1.40, 0.0]),
         "right_shoulder": np.array([-0.18, 1.40, 0.0])}
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    for tl, P in ((fo, P1), (dl, P2)):
        lms = []
        for name, Xw in X.items():
            u, v = _project(P, Xw)
            lms.append(Landmark(name=name, x=u, y=v, z=0.0, visibility=0.99))
        tl.times_s.append(0.0); tl.frames.append(lms)
    out = reconstruct(fo, dl, cal)
    assert len(out) == 1
    by = {l.name: l for l in out.frames[0]}
    assert np.allclose([by["left_shoulder"].x, by["left_shoulder"].y,
                        by["left_shoulder"].z], [0.18, 1.40, 0.0], atol=1e-5)


def test_reconstruct_drops_low_visibility_landmark():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    # one landmark visible in only one view -> not triangulated
    fo.times_s.append(0.0)
    fo.frames.append([Landmark("nose", 480, 300, 0, 0.99)])
    dl.times_s.append(0.0)
    dl.frames.append([Landmark("nose", 480, 300, 0, 0.1)])   # low vis in DL
    out = reconstruct(fo, dl, cal, min_visibility=0.5)
    assert out.frames[0] == [] or out.frames[0] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest vision/tests/test_reconstruct.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement triangulation + reconstruct**

```python
# vision/threed/reconstruct.py
"""Triangulate the two synced per-view 2D pose timelines into a metric 3D
timeline. Frames are assumed synchronized (composite source), so face_on.frames[i]
and down_line.frames[i] are the same instant.
"""
from typing import List, Optional

import cv2
import numpy as np

from store.models import Landmark, Landmark3D
from vision.threed.types import Pose3DTimeline

MIN_VISIBILITY = 0.5


def triangulate_point(P1, P2, pt1, pt2):
    """DLT triangulation of one correspondence. Returns 3D np.array (meters)."""
    a = np.array(pt1, dtype=float).reshape(2, 1)
    b = np.array(pt2, dtype=float).reshape(2, 1)
    Xh = cv2.triangulatePoints(np.asarray(P1, float), np.asarray(P2, float), a, b)
    return (Xh[:3] / Xh[3]).ravel()


def _by_name(frame: Optional[List[Landmark]]):
    return {l.name: l for l in frame} if frame else {}


def reconstruct(face_on, down_line, calibration,
                min_visibility: float = MIN_VISIBILITY) -> Pose3DTimeline:
    """Per composite frame, triangulate every landmark visible (>= min_visibility)
    in BOTH views. Confidence = min of the two visibilities. Frames with no
    triangulated landmark become an empty list."""
    P1, P2 = calibration.projection_matrices()
    out = Pose3DTimeline()
    n = min(len(face_on), len(down_line))
    for i in range(n):
        fo, dl = _by_name(face_on.frames[i]), _by_name(down_line.frames[i])
        lms3d: List[Landmark3D] = []
        for name in fo.keys() & dl.keys():
            a, b = fo[name], dl[name]
            if a.visibility < min_visibility or b.visibility < min_visibility:
                continue
            X = triangulate_point(P1, P2, (a.x, a.y), (b.x, b.y))
            lms3d.append(Landmark3D(name=name, x=float(X[0]), y=float(X[1]),
                                    z=float(X[2]),
                                    confidence=float(min(a.visibility,
                                                         b.visibility))))
        out.times_s.append(face_on.times_s[i] if i < len(face_on.times_s) else 0.0)
        out.frames.append(lms3d)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest vision/tests/test_reconstruct.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Commit**

```bash
git add vision/threed/reconstruct.py vision/tests/test_reconstruct.py
git commit -m "feat(vision/threed): DLT triangulation + reconstruct timeline"
```

---

## Task 5: 3D angle helpers (`metrics/geometry3d.py`)

**Files:**
- Create: `metrics/geometry3d.py`
- Test: `metrics/tests/test_geometry3d.py`

**Context:** Pure vector math used by both 3D metric defs. `turn_about_axis` measures the signed rotation of a segment relative to its address orientation, about the vertical axis (projected onto the ground plane). `tilt_from_vertical` gives the 3D side-bend magnitude.

- [ ] **Step 1: Write the failing test**

```python
# metrics/tests/test_geometry3d.py
import math
import numpy as np
from metrics import geometry3d as g3


def test_turn_about_axis_90_degrees():
    up = np.array([0.0, 1.0, 0.0])
    addr = np.array([1.0, 0.0, 0.0])      # shoulder line along target line
    rotated = np.array([0.0, 0.0, 1.0])   # turned 90 deg about vertical
    assert abs(abs(g3.turn_about_axis(addr, rotated, up)) - 90.0) < 1e-6


def test_turn_about_axis_zero_at_address():
    up = np.array([0.0, 1.0, 0.0])
    v = np.array([1.0, 0.0, 0.3])
    assert abs(g3.turn_about_axis(v, v, up)) < 1e-6


def test_tilt_from_vertical_magnitude():
    up = np.array([0.0, 1.0, 0.0])
    # shoulder line 30 deg above horizontal in the X-Y plane
    v = np.array([math.cos(math.radians(30)), math.sin(math.radians(30)), 0.0])
    assert abs(g3.tilt_from_horizontal(v, up) - 30.0) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest metrics/tests/test_geometry3d.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helpers**

```python
# metrics/geometry3d.py
"""3D vector helpers for triangulated-pose metrics. World frame: up = +Y,
target_line = +X, depth = +Z. All inputs are numpy 3-vectors."""
import math
import numpy as np


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def project_to_plane(v, axis):
    """Component of v orthogonal to `axis` (the plane with normal `axis`)."""
    axis = _unit(axis)
    return v - np.dot(v, axis) * axis


def turn_about_axis(seg_address, seg_current, up):
    """Signed angle (deg) the segment rotated about `up`, from its address
    orientation to current. Both projected onto the plane normal to `up`."""
    a = _unit(project_to_plane(np.asarray(seg_address, float), up))
    b = _unit(project_to_plane(np.asarray(seg_current, float), up))
    cross = np.cross(a, b)
    sin = np.dot(_unit(np.asarray(up, float)), cross)
    cos = np.dot(a, b)
    return math.degrees(math.atan2(sin, cos))


def tilt_from_horizontal(seg, up):
    """Magnitude (deg) the segment is tilted away from horizontal (the plane
    normal to `up`). 0 = level, 90 = aligned with `up`."""
    seg = np.asarray(seg, float)
    up = _unit(np.asarray(up, float))
    horiz = project_to_plane(seg, up)
    return math.degrees(math.atan2(abs(np.dot(seg, up)),
                                   np.linalg.norm(horiz)))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest metrics/tests/test_geometry3d.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add metrics/geometry3d.py metrics/tests/test_geometry3d.py
git commit -m "feat(metrics): 3D angle helpers (turn-about-axis, tilt-from-horizontal)"
```

---

## Task 6: `MetricContext.pose_3d` + `pose_3d_at`

**Files:**
- Modify: `metrics/context.py`
- Test: `metrics/tests/test_context_3d.py`

**Context:** `build_context` (in `metrics/context.py`) already loads 2D pose per view + a `(view, kind) -> frame_index` map. Add a `pose_3d` dict `{frame_index: [Landmark3D]}` (loaded via `repo.get_pose_3d_frames`) and `pose_3d_at(kind)` that resolves the moment frame (using either view — synced composite shares the index) and returns the 3D pose there.

- [ ] **Step 1: Write the failing test**

```python
# metrics/tests/test_context_3d.py
from metrics.context import MetricContext
from store.models import Landmark3D


def test_pose_3d_at_resolves_moment_frame():
    ctx = MetricContext(
        swing_id=1, player=None, ppi=0.0, fps=30.0,
        _pose={}, _moment_frame={("face_on", "top"): 40, ("down_line", "top"): 40},
        pose_3d={40: [Landmark3D("left_shoulder", 0.2, 1.4, 0.0, 0.9)]},
    )
    pose = ctx.pose_3d_at("top")
    assert pose is not None and pose[0].name == "left_shoulder"
    assert ctx.pose_3d_at("impact") is None    # no moment / no 3d frame
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest metrics/tests/test_context_3d.py -v`
Expected: FAIL — `MetricContext.__init__() got an unexpected keyword argument 'pose_3d'`.

- [ ] **Step 3: Extend `MetricContext` and `build_context`**

In `metrics/context.py`, add `pose_3d` to the dataclass (after `_moment_frame`), and an accessor. The dataclass currently ends with `_moment_frame`; add:

```python
    # frame_index -> [Landmark3D]  (empty when no 3D reconstruction exists)
    _pose3d: Dict[int, List["Landmark3D"]] = None  # set in __post_init__/build

    def pose_3d_at(self, kind: str):
        """3D pose at the moment `kind` (uses either view's frame index; the
        synced composite shares it). None if missing."""
        for view in ("face_on", "down_line"):
            idx = self._moment_frame.get((view, kind))
            if idx is not None and self._pose3d and idx in self._pose3d:
                return self._pose3d[idx]
        return None
```

Make the constructor accept it. Change the dataclass to take `pose_3d` via a field and store it. Simplest: add a keyword-able field `pose_3d` and assign to `_pose3d`. Replace the field declaration with:

```python
    pose_3d: Dict[int, List["Landmark3D"]] = field(default_factory=dict)
```

and use `self.pose_3d` in `pose_3d_at` instead of `self._pose3d`:

```python
    def pose_3d_at(self, kind: str):
        for view in ("face_on", "down_line"):
            idx = self._moment_frame.get((view, kind))
            if idx is not None and idx in (self.pose_3d or {}):
                return self.pose_3d[idx]
        return None
```

Add `from dataclasses import field` if not present, and `from store.models import Landmark3D` to the imports.

In `build_context`, after building `moment_frame`, load 3D:

```python
    pose_3d = repo.get_pose_3d_frames(conn, swing_id)   # {} when none
```

and pass `pose_3d=pose_3d` into the `MetricContext(...)` constructor call.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest metrics/tests/test_context_3d.py -v`
Expected: PASS.

- [ ] **Step 5: Run the existing metrics suite (no regressions)**

Run: `python -m pytest metrics/ -q`
Expected: PASS (existing 2D metric tests unaffected — `pose_3d` defaults to `{}`).

- [ ] **Step 6: Commit**

```bash
git add metrics/context.py metrics/tests/test_context_3d.py
git commit -m "feat(metrics): MetricContext.pose_3d + pose_3d_at"
```

---

## Task 7: 3D rotation metrics (`metrics/defs/rotation_3d.py`)

**Files:**
- Create: `metrics/defs/rotation_3d.py`
- Modify: `metrics/defs/__init__.py` (import the new module)
- Test: `metrics/tests/test_rotation_3d.py`

**Context:** New `MetricDef`s computing turn from 3D, relative to the address pose, about the world up axis (+Y). They no-op (`return []`) when `pose_3d_at` is empty, so the registry is safe without 3D. X-factor = shoulder turn − hip turn at top; stretch = peak X-factor over top→impact minus X-factor at top.

- [ ] **Step 1: Write the failing test**

```python
# metrics/tests/test_rotation_3d.py
import numpy as np
from metrics.context import MetricContext
from metrics.defs import rotation_3d as r3
from store.models import Landmark3D


def _ctx(pose3d, moments):
    return MetricContext(swing_id=1, player=None, ppi=0.0, fps=30.0,
                         _pose={}, _moment_frame=moments, pose_3d=pose3d)


def _shoulders(turn_deg):
    th = np.radians(turn_deg)
    # shoulder line in ground plane, rotated `turn_deg` about +Y from +X
    L = np.array([np.cos(th), 1.4, np.sin(th)])
    R = -L + np.array([0, 2.8, 0])     # mirror across center, same height
    return [Landmark3D("left_shoulder", *L, 0.9),
            Landmark3D("right_shoulder", *R, 0.9)]


def _hips(turn_deg):
    th = np.radians(turn_deg)
    L = np.array([0.5 * np.cos(th), 0.9, 0.5 * np.sin(th)])
    R = -L + np.array([0, 1.8, 0])
    return [Landmark3D("left_hip", *L, 0.9), Landmark3D("right_hip", *R, 0.9)]


def test_shoulder_turn_3d_relative_to_address():
    pose3d = {0: _shoulders(0) + _hips(0),       # address
              40: _shoulders(85) + _hips(45)}    # top
    moments = {("face_on", "address"): 0, ("face_on", "top"): 40}
    ctx = _ctx(pose3d, moments)
    out = {m.name + "@" + m.context: m for m in r3.shoulder_turn(ctx)}
    assert abs(abs(out["shoulder_turn_deg@top"].value) - 85.0) < 1.0
    assert out["shoulder_turn_deg@top"].method.startswith("triangulated_3d")


def test_x_factor_is_shoulder_minus_hip_at_top():
    pose3d = {0: _shoulders(0) + _hips(0), 40: _shoulders(85) + _hips(45)}
    moments = {("face_on", "address"): 0, ("face_on", "top"): 40}
    ctx = _ctx(pose3d, moments)
    xf = {m.context: m for m in r3.x_factor(ctx)}
    assert abs(abs(xf["top"].value) - 40.0) < 1.5


def test_rotation_3d_noops_without_pose_3d():
    ctx = _ctx({}, {("face_on", "top"): 40})
    assert r3.shoulder_turn(ctx) == []
    assert r3.x_factor(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest metrics/tests/test_rotation_3d.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the 3D rotation defs**

```python
# metrics/defs/rotation_3d.py
"""True 3D shoulder/hip turn + X-factor from triangulated pose, relative to
address, about world up (+Y). No-ops when pose_3d is absent so the 2D registry
is unaffected. Same metric names as the 2D versions; method='triangulated_3d'.
"""
from typing import List, Optional

import numpy as np

from store.models import Metric
from metrics import geometry3d as g3
from metrics.registry import MetricDef, register

UP = np.array([0.0, 1.0, 0.0])
METHOD = "triangulated_3d;confidence=medium"
REPORT = ("top", "impact")


def _vec(pose, a_name, b_name) -> Optional[np.ndarray]:
    by = {l.name: l for l in pose}
    a, b = by.get(a_name), by.get(b_name)
    if a is None or b is None:
        return None
    return np.array([b.x - a.x, b.y - a.y, b.z - a.z])


def _turn(ctx, name, a_name, b_name) -> List[Metric]:
    addr = ctx.pose_3d_at("address")
    if addr is None:
        return []
    v0 = _vec(addr, a_name, b_name)
    if v0 is None:
        return []
    out: List[Metric] = []
    for kind in REPORT:
        pose = ctx.pose_3d_at(kind)
        if pose is None:
            continue
        v = _vec(pose, a_name, b_name)
        if v is None:
            continue
        deg = g3.turn_about_axis(v0, v, UP)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_turn(ctx) -> List[Metric]:
    return _turn(ctx, "shoulder_turn_deg", "left_shoulder", "right_shoulder")


def hip_turn(ctx) -> List[Metric]:
    return _turn(ctx, "hip_turn_deg", "left_hip", "right_hip")


def _turn_value(ctx, a_name, b_name, kind) -> Optional[float]:
    addr = ctx.pose_3d_at("address")
    pose = ctx.pose_3d_at(kind)
    if addr is None or pose is None:
        return None
    v0, v = _vec(addr, a_name, b_name), _vec(pose, a_name, b_name)
    if v0 is None or v is None:
        return None
    return g3.turn_about_axis(v0, v, UP)


def x_factor(ctx) -> List[Metric]:
    sh = _turn_value(ctx, "left_shoulder", "right_shoulder", "top")
    hp = _turn_value(ctx, "left_hip", "right_hip", "top")
    if sh is None or hp is None:
        return []
    return [Metric(swing_id=ctx.swing_id, name="x_factor_deg", context="top",
                  value=sh - hp, unit="deg", method=METHOD)]


def x_factor_stretch(ctx) -> List[Metric]:
    """Peak X-factor over top->impact frames minus X-factor at top. Needs the
    full 3D timeline between the top and impact moment frames."""
    top = ctx.frame_index_for("face_on", "top") or ctx.frame_index_for("down_line", "top")
    imp = ctx.frame_index_for("face_on", "impact") or ctx.frame_index_for("down_line", "impact")
    addr = ctx.pose_3d_at("address")
    if top is None or imp is None or addr is None or not ctx.pose_3d:
        return []
    v0s = _vec(addr, "left_shoulder", "right_shoulder")
    v0h = _vec(addr, "left_hip", "right_hip")
    if v0s is None or v0h is None:
        return []
    xf_top = None
    peak = None
    lo, hi = min(top, imp), max(top, imp)
    for idx in range(lo, hi + 1):
        pose = ctx.pose_3d.get(idx)
        if not pose:
            continue
        vs = _vec(pose, "left_shoulder", "right_shoulder")
        vh = _vec(pose, "left_hip", "right_hip")
        if vs is None or vh is None:
            continue
        xf = g3.turn_about_axis(v0s, vs, UP) - g3.turn_about_axis(v0h, vh, UP)
        if idx == top:
            xf_top = xf
        peak = xf if peak is None or abs(xf) > abs(peak) else peak
    if xf_top is None or peak is None:
        return []
    return [Metric(swing_id=ctx.swing_id, name="x_factor_stretch_deg",
                  context="downswing", value=abs(peak) - abs(xf_top),
                  unit="deg", method=METHOD)]


register(MetricDef(name="shoulder_turn_deg", view="threed",
                   contexts=REPORT, fn=shoulder_turn))
register(MetricDef(name="hip_turn_deg", view="threed",
                   contexts=REPORT, fn=hip_turn))
register(MetricDef(name="x_factor_deg", view="threed",
                   contexts=("top",), fn=x_factor))
register(MetricDef(name="x_factor_stretch_deg", view="threed",
                   contexts=("downswing",), fn=x_factor_stretch))
```

- [ ] **Step 4: Register the module**

In `metrics/defs/__init__.py`, add an import so `register()` runs (match the existing import style for `tilt`, `rotation`, etc.):

```python
from metrics.defs import rotation_3d  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest metrics/tests/test_rotation_3d.py -v`
Expected: PASS (all three).

- [ ] **Step 6: Commit**

```bash
git add metrics/defs/rotation_3d.py metrics/defs/__init__.py metrics/tests/test_rotation_3d.py
git commit -m "feat(metrics): 3D shoulder/hip turn + X-factor + stretch"
```

---

## Task 8: 3D side-bend metrics (`metrics/defs/sidebend_3d.py`)

**Files:**
- Create: `metrics/defs/sidebend_3d.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_sidebend_3d.py`

**Context:** Un-foreshortened shoulder/hip tilt from 3D at **top + impact** only (address stays 2D). Same names (`shoulder_tilt_deg`/`hip_tilt_deg`), `method="triangulated_3d"`. Tilt = magnitude from horizontal (plane normal to up), via `geometry3d.tilt_from_horizontal`.

- [ ] **Step 1: Write the failing test**

```python
# metrics/tests/test_sidebend_3d.py
import math
import numpy as np
from metrics.context import MetricContext
from metrics.defs import sidebend_3d as s3
from store.models import Landmark3D


def _ctx(pose3d, moments):
    return MetricContext(swing_id=1, player=None, ppi=0.0, fps=30.0,
                         _pose={}, _moment_frame=moments, pose_3d=pose3d)


def test_shoulder_tilt_3d_at_impact_known_angle():
    th = math.radians(36)
    L = np.array([math.cos(th), 1.4 + math.sin(th), 0.0])
    R = np.array([-math.cos(th), 1.4 - math.sin(th), 0.0])
    pose = [Landmark3D("left_shoulder", *L, 0.9),
            Landmark3D("right_shoulder", *R, 0.9)]
    ctx = _ctx({50: pose}, {("face_on", "impact"): 50})
    out = {m.context: m for m in s3.shoulder_tilt_3d(ctx)}
    assert abs(out["impact"].value - 36.0) < 1.0
    assert out["impact"].method.startswith("triangulated_3d")
    assert "address" not in out          # 3D side-bend only at top/impact


def test_sidebend_3d_noops_without_pose_3d():
    ctx = _ctx({}, {("face_on", "impact"): 50})
    assert s3.shoulder_tilt_3d(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest metrics/tests/test_sidebend_3d.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the 3D side-bend defs**

```python
# metrics/defs/sidebend_3d.py
"""Un-foreshortened 3D shoulder/hip side-bend (tilt from horizontal) at top +
impact. Same names as the 2D tilt metrics; method='triangulated_3d'. No-ops when
pose_3d is absent. Address tilt stays 2D (it is already square-accurate)."""
from typing import List, Optional

import numpy as np

from store.models import Metric
from metrics import geometry3d as g3
from metrics.registry import MetricDef, register

UP = np.array([0.0, 1.0, 0.0])
METHOD = "triangulated_3d;confidence=medium"
CONTEXTS = ("top", "impact")


def _vec(pose, a_name, b_name) -> Optional[np.ndarray]:
    by = {l.name: l for l in pose}
    a, b = by.get(a_name), by.get(b_name)
    if a is None or b is None:
        return None
    return np.array([b.x - a.x, b.y - a.y, b.z - a.z])


def _tilt(ctx, name, a_name, b_name) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_3d_at(kind)
        if pose is None:
            continue
        v = _vec(pose, a_name, b_name)
        if v is None:
            continue
        deg = g3.tilt_from_horizontal(v, UP)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_tilt_3d(ctx) -> List[Metric]:
    return _tilt(ctx, "shoulder_tilt_deg", "left_shoulder", "right_shoulder")


def hip_tilt_3d(ctx) -> List[Metric]:
    return _tilt(ctx, "hip_tilt_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_tilt_deg", view="threed",
                   contexts=CONTEXTS, fn=shoulder_tilt_3d))
register(MetricDef(name="hip_tilt_deg", view="threed",
                   contexts=CONTEXTS, fn=hip_tilt_3d))
```

- [ ] **Step 4: Register the module**

In `metrics/defs/__init__.py`, add:

```python
from metrics.defs import sidebend_3d  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest metrics/tests/test_sidebend_3d.py -v`
Expected: PASS.

- [ ] **Step 6: Run the full metrics suite**

Run: `python -m pytest metrics/ -q`
Expected: PASS. Note: there are now two `shoulder_tilt_deg`/`hip_tilt_deg` defs registered (2D + 3D). They emit different `method`s and different contexts (3D only top/impact); with no `pose_3d` the 3D ones no-op, so existing tests are unaffected.

- [ ] **Step 7: Commit**

```bash
git add metrics/defs/sidebend_3d.py metrics/defs/__init__.py metrics/tests/test_sidebend_3d.py
git commit -m "feat(metrics): 3D un-foreshortened side-bend at top/impact"
```

---

## Task 9: Pipeline integration (reconstruct + persist when enabled)

**Files:**
- Modify: `vision/constants.py` (config)
- Modify: `vision/pipeline.py` (`process_video` gains `calibration` arg; reconstruct + persist)
- Test: `vision/tests/test_pipeline_3d.py`

**Context:** `process_video` (in `vision/pipeline.py`) already builds `down_line, face_on` timelines and persists each swing. Add an optional `calibration` parameter: when provided, after persisting a swing's 2D pose, reconstruct the 3D timeline for that swing's frame window and persist it via `repo.save_pose_3d_frames`. When `calibration is None`, behavior is unchanged.

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_pipeline_3d.py
import numpy as np
from vision.threed.reconstruct import reconstruct
from vision.threed.calibration import AssumedGeometryCalibration
from vision.threed import pipeline3d
from vision.types import PoseTimeline
from store.models import Landmark


def _proj(P, X):
    uvw = P @ np.array([X[0], X[1], X[2], 1.0]); return uvw[0]/uvw[2], uvw[1]/uvw[2]


def test_pipeline3d_reconstructs_window_to_index_map():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    pts = {"left_shoulder": np.array([0.18, 1.4, 0.0]),
           "right_shoulder": np.array([-0.18, 1.4, 0.0])}
    for k in range(3):
        for tl, P in ((fo, P1), (dl, P2)):
            tl.times_s.append(k / 30.0)
            tl.frames.append([Landmark(n, *_proj(P, X), 0.0, 0.99)
                              for n, X in pts.items()])
    frames_by_index = pipeline3d.reconstruct_window(fo, dl, cal,
                                                    start_index=0, end_index=2)
    assert set(frames_by_index.keys()) == {0, 1, 2}
    by = {l.name: l for l in frames_by_index[0]}
    assert abs(by["left_shoulder"].x - 0.18) < 1e-4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest vision/tests/test_pipeline_3d.py -v`
Expected: FAIL — `ModuleNotFoundError: vision.threed.pipeline3d`.

- [ ] **Step 3: Add a small reconstruction-window helper**

```python
# vision/threed/pipeline3d.py
"""Glue between the per-swing frame window and the 3D reconstructor: reconstruct
only the swing's frames and key them by absolute composite frame index (so they
align with the moments the metrics read)."""
from typing import Dict, List

from store.models import Landmark3D
from vision.threed.reconstruct import reconstruct


def reconstruct_window(face_on, down_line, calibration,
                       start_index: int, end_index: int) -> Dict[int, List[Landmark3D]]:
    """Triangulate frames [start_index, end_index] (inclusive) and return
    {absolute_frame_index: [Landmark3D]}. Empty 3D frames are skipped."""
    tl = reconstruct(face_on, down_line, calibration)
    out: Dict[int, List[Landmark3D]] = {}
    for idx in range(start_index, min(end_index, len(tl) - 1) + 1):
        lms = tl.frames[idx] if idx < len(tl.frames) else None
        if lms:
            out[idx] = lms
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest vision/tests/test_pipeline_3d.py -v`
Expected: PASS.

- [ ] **Step 5: Wire it into `process_video`**

In `vision/pipeline.py`, add `calibration=None` to the `process_video` signature, and after the existing `swing_id = persist_swing(...)` call (around line 80-85), insert:

```python
            if calibration is not None:
                frames_3d = reconstruct_window(
                    face_on, down_line, calibration,
                    window.start_index, window.end_index)
                if frames_3d:
                    from store import repo
                    repo.save_pose_3d_frames(conn, swing_id, frames_3d)
```

Add the import at the top of `vision/pipeline.py`:

```python
from vision.threed.pipeline3d import reconstruct_window
```

- [ ] **Step 6: Add config constants**

In `vision/constants.py`, add:

```python
# 3D reconstruction (two-camera triangulation). Off unless a Calibration is
# passed to process_video; this documents the default focal/distance the
# AssumedGeometry provider uses when no checkerboard calibration exists.
THREED_DEFAULT_CAMERA_DISTANCE_M = 4.0
```

- [ ] **Step 7: Run the vision suite**

Run: `python -m pytest vision/ -q`
Expected: PASS (existing pipeline tests pass `calibration=None` implicitly → unchanged behavior).

- [ ] **Step 8: Commit**

```bash
git add vision/threed/pipeline3d.py vision/pipeline.py vision/constants.py vision/tests/test_pipeline_3d.py
git commit -m "feat(vision): optional 3D reconstruction + persist in pipeline"
```

---

## Task 10: `smooth_swing.mov` validation + coach wiring to GolfTEC `needs_3d`

**Files:**
- Create: `coach/golftec.py`
- Create: `coach/tests/test_golftec.py`
- Create: `scripts/validate_3d_smooth_swing.py` (manual validation, not a unit test)

**Context:** Two pieces: (a) a coach loader/comparator for `golftec_reference.json` that only compares a live value when it is valid (2D-square OR 3D-present); (b) a runnable validation against `smooth_swing.mov` (rotate to landscape, run the pipeline with `AssumedGeometryCalibration`, print turn/X-factor and check they are in a plausible range).

- [ ] **Step 1: Write the failing test (coach comparator)**

```python
# coach/tests/test_golftec.py
from coach import golftec


def test_load_golftec_reference_has_turn_target():
    ref = golftec.load()
    assert ref["shoulder_turn_deg"]["value_by_phase"]["top"] == 89


def test_compare_uses_target_when_3d_available():
    ref = golftec.load()
    # shoulder turn @ top is needs_3d -> only comparable when has_3d=True
    r = golftec.compare("shoulder_turn_deg", "top", 80.0, has_3d=True, ref=ref)
    assert r["comparable"] is True
    assert abs(r["delta"] - (80.0 - 89.0)) < 1e-9
    r2 = golftec.compare("shoulder_turn_deg", "top", 80.0, has_3d=False, ref=ref)
    assert r2["comparable"] is False
    assert r2["reason"] == "needs_3d"


def test_compare_square_position_works_in_2d():
    ref = golftec.load()
    # shoulder tilt @ address is two_d_comparable_now -> comparable without 3D
    r = golftec.compare("shoulder_tilt_deg", "address", 12.0, has_3d=False, ref=ref)
    assert r["comparable"] is True
    assert abs(r["target"] - 10.0) < 1e-9
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest coach/tests/test_golftec.py -v`
Expected: FAIL — `ModuleNotFoundError: coach.golftec`.

- [ ] **Step 3: Implement the loader/comparator**

```python
# coach/golftec.py
"""Load the authoritative GolfTEC reference and compare a live metric value to
its tour-pro target, honoring the 2D-vs-3D gate: a (metric, phase) is only
comparable when it is two_d_comparable_now OR a 3D value is available.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "norms", "pro_reference",
                     "golftec_reference.json")


def load(path=None):
    with open(path or _PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def compare(name, context, value, has_3d=False, ref=None):
    """Return {comparable, target, delta, reason}. comparable is False (with a
    reason) when the metric/phase needs 3D and none is available, or when the
    metric/phase is unknown."""
    ref = load() if ref is None else ref
    entry = ref.get(name)
    if entry is None or "contexts" not in entry:
        return {"comparable": False, "target": None, "delta": None,
                "reason": "no_golftec_target"}
    ctx = entry["contexts"].get(context)
    if ctx is None:
        return {"comparable": False, "target": None, "delta": None,
                "reason": "no_phase_target"}
    target = ctx["value"]
    if ctx.get("two_d_comparable_now") or has_3d:
        return {"comparable": True, "target": target,
                "delta": value - target, "reason": None}
    return {"comparable": False, "target": target, "delta": None,
            "reason": "needs_3d"}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest coach/tests/test_golftec.py -v`
Expected: PASS.

- [ ] **Step 5: Write the manual `smooth_swing.mov` validation script**

```python
# scripts/validate_3d_smooth_swing.py
"""Manual validation (NOT a unit test): run the 3D pipeline on smooth_swing.mov
with the approximate calibration and print turn/X-factor. smooth_swing.mov is a
direct-export synced side-by-side clip (rotated 90 deg portrait -> rotate to
landscape first). Pass if shoulder turn @ top is ~80-95 deg and X-factor > 0.

Usage: python scripts/validate_3d_smooth_swing.py path/to/smooth_swing.mov
"""
import sys

from store import db as dbmod, repo
from vision.pipeline import process_video
from vision.threed.calibration import AssumedGeometryCalibration
from metrics.compute import compute_metrics


def main(video_path):
    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    pid = repo.get_or_create_player(conn, "Pro", 70.0, "R").id
    sid = repo.create_session(conn, pid).id
    # NOTE: smooth_swing.mov is portrait-rotated; rotate to landscape before this
    # (e.g. ffmpeg -vf "transpose=1") so the side-by-side split is correct.
    cal = AssumedGeometryCalibration(image_width=1214, image_height=1080,
                                     height_in=70.0)
    results = process_video(conn, video_path, player_id=pid, session_id=sid,
                            single_swing=True, calibration=cal)
    for res in results:
        metrics = compute_metrics(conn, res.swing_id)
        wanted = {(m.name, m.context): m.value for m in metrics
                  if m.method and m.method.startswith("triangulated_3d")}
        print("swing", res.swing_id)
        for k in sorted(wanted):
            print(f"   {k[0]}@{k[1]} = {wanted[k]:.1f} deg")
        st = wanted.get(("shoulder_turn_deg", "top"))
        if st is not None:
            ok = 70.0 <= abs(st) <= 100.0
            print(f"   shoulder turn @ top plausible (70-100): {ok}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "smooth_swing.mov")
```

- [ ] **Step 6: Run the validation manually (requires the clip + landscape rotation)**

Run: `python scripts/validate_3d_smooth_swing.py <landscape smooth_swing.mov>`
Expected: prints 3D metrics; shoulder turn @ top reported as plausible. (Approximate calibration → judge the *range/trend*, not exact degrees. If implausible, revisit `AssumedGeometryCalibration` camera distance/focal.)

- [ ] **Step 7: Commit**

```bash
git add coach/golftec.py coach/tests/test_golftec.py scripts/validate_3d_smooth_swing.py
git commit -m "feat(coach): GolfTEC comparator (2D/3D gate) + smooth_swing 3D validation"
```

---

## Task 11: `CheckerboardCalibration` (DEFERRED — needs the bay calibration capture)

> **Do this last, after the physical bay exists and the calibration capture (spec §3.3) is done.** Until then the pipeline runs on `AssumedGeometryCalibration`.

**Files:**
- Modify: `vision/threed/calibration.py` (add provider)
- Create: `scripts/calibrate_bay_cameras.py` (one-time capture → calib file)
- Test: `vision/tests/test_checkerboard_calibration.py`

**Context:** Production accuracy. Capture a checkerboard from both bay views, run `cv2.stereoCalibrate` to get intrinsics + relative pose, save to a calib file the pipeline loads. The provider just loads that file and exposes the same `projection_matrices()` / `world_frame()` interface (so swapping it in requires no change to reconstruct/metrics).

- [ ] **Step 1: Write the failing test (round-trip a saved calib file)**

```python
# vision/tests/test_checkerboard_calibration.py
import json
import numpy as np
from vision.threed.calibration import CheckerboardCalibration


def test_loads_saved_calibration_and_projects(tmp_path):
    calib = {
        "image_width": 960, "image_height": 1080,
        "K_face_on": [[960, 0, 480], [0, 960, 540], [0, 0, 1]],
        "K_down_line": [[960, 0, 480], [0, 960, 540], [0, 0, 1]],
        "R_face_on": [[1, 0, 0], [0, -1, 0], [0, 0, -1]],
        "t_face_on": [0, 0, 4.0],
        "R_down_line": [[0, 0, 1], [0, -1, 0], [-1, 0, 0]],
        "t_down_line": [0, 0, 4.0],
        "up": [0, 1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }
    p = tmp_path / "bay_calib.json"
    p.write_text(json.dumps(calib))
    cal = CheckerboardCalibration(str(p))
    P_fo, P_dl = cal.projection_matrices()
    assert P_fo.shape == (3, 4) and P_dl.shape == (3, 4)
    assert cal.confidence == "high"
    # world origin projects to image center
    uvw = P_fo @ np.array([0, 0, 0, 1.0])
    assert abs(uvw[0] / uvw[2] - 480) < 1e-6
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest vision/tests/test_checkerboard_calibration.py -v`
Expected: FAIL — `cannot import name 'CheckerboardCalibration'`.

- [ ] **Step 3: Implement the provider**

Append to `vision/threed/calibration.py`:

```python
import json


class CheckerboardCalibration(Calibration):
    """Loads a saved OpenCV stereo calibration (produced by
    scripts/calibrate_bay_cameras.py). HIGH confidence."""
    confidence = "high"

    def __init__(self, calib_path):
        with open(calib_path, "r", encoding="utf-8") as f:
            c = json.load(f)
        self._c = c
        self.K_fo = np.array(c["K_face_on"], float)
        self.K_dl = np.array(c["K_down_line"], float)
        self.R_fo = np.array(c["R_face_on"], float)
        self.t_fo = np.array(c["t_face_on"], float)
        self.R_dl = np.array(c["R_down_line"], float)
        self.t_dl = np.array(c["t_down_line"], float)

    def projection_matrices(self):
        return (_projection(self.K_fo, self.R_fo, self.t_fo),
                _projection(self.K_dl, self.R_dl, self.t_dl))

    def world_frame(self):
        return {"origin": np.array([0.0, 0.0, 0.0]),
                "up": np.array(self._c["up"], float),
                "target_line": np.array(self._c["target_line"], float),
                "depth": np.array(self._c["depth"], float)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest vision/tests/test_checkerboard_calibration.py -v`
Expected: PASS.

- [ ] **Step 5: Write the one-time bay-capture script**

```python
# scripts/calibrate_bay_cameras.py
"""ONE-TIME bay calibration (run after the cameras are fixed-mounted).

Capture N synced composite frames of a checkerboard held at varied positions/
angles across the hitting area. This detects the board in each view, runs
cv2.stereoCalibrate, and writes bay_calib.json for CheckerboardCalibration.

Usage: python scripts/calibrate_bay_cameras.py <dir-of-composite-pngs> \
         --cols 9 --rows 6 --square-mm 25 --split 0.5 --out bay_calib.json

NOTE: cameras must NOT move after this; a bump invalidates the calibration.
"""
import argparse, glob, json, os
import cv2
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--cols", type=int, default=9)
    ap.add_argument("--rows", type=int, default=6)
    ap.add_argument("--square-mm", type=float, default=25.0)
    ap.add_argument("--split", type=float, default=0.5,
                    help="composite split fraction; left=down_line, right=face_on")
    ap.add_argument("--out", default="bay_calib.json")
    args = ap.parse_args()

    pattern = (args.cols, args.rows)
    objp = np.zeros((args.cols * args.rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:args.cols, 0:args.rows].T.reshape(-1, 2)
    objp *= (args.square_mm / 1000.0)   # meters

    obj_pts, fo_pts, dl_pts = [], [], []
    w = h = None
    for path in sorted(glob.glob(os.path.join(args.frames_dir, "*.png"))):
        img = cv2.imread(path)
        H, W = img.shape[:2]
        mid = int(W * args.split)
        dl_img, fo_img = img[:, :mid], img[:, mid:]
        g_dl = cv2.cvtColor(dl_img, cv2.COLOR_BGR2GRAY)
        g_fo = cv2.cvtColor(fo_img, cv2.COLOR_BGR2GRAY)
        ok_dl, c_dl = cv2.findChessboardCorners(g_dl, pattern)
        ok_fo, c_fo = cv2.findChessboardCorners(g_fo, pattern)
        if ok_dl and ok_fo:
            obj_pts.append(objp); dl_pts.append(c_dl); fo_pts.append(c_fo)
            w, h = g_fo.shape[1], g_fo.shape[0]
    if len(obj_pts) < 8:
        raise SystemExit(f"only {len(obj_pts)} usable pairs; need >= 8")

    _, K_fo, d_fo, _, _ = cv2.calibrateCamera(obj_pts, fo_pts, (w, h), None, None)
    _, K_dl, d_dl, _, _ = cv2.calibrateCamera(obj_pts, dl_pts, (w, h), None, None)
    _, K_fo, d_fo, K_dl, d_dl, R, T, _, _ = cv2.stereoCalibrate(
        obj_pts, fo_pts, dl_pts, K_fo, d_fo, K_dl, d_dl, (w, h),
        flags=cv2.CALIB_FIX_INTRINSIC)

    # Face-on as world reference (R=I, t=0); down_line = [R|T] relative to it.
    calib = {
        "image_width": w, "image_height": h,
        "K_face_on": K_fo.tolist(), "K_down_line": K_dl.tolist(),
        "R_face_on": np.eye(3).tolist(), "t_face_on": [0.0, 0.0, 0.0],
        "R_down_line": R.tolist(), "t_down_line": T.ravel().tolist(),
        # world axes in the face-on camera frame; refine from the board pose if
        # the board was placed on the ground aligned to the target line.
        "up": [0, -1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(calib, f, indent=2)
    print(f"wrote {args.out} from {len(obj_pts)} checkerboard pairs")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Switch the pipeline to the checkerboard provider + re-validate**

Once `bay_calib.json` exists, construct `CheckerboardCalibration("bay_calib.json")` and pass it to `process_video(... calibration=...)`. Re-run a known-good pro swing and confirm shoulder turn @ top is within tolerance of GolfTEC 89° / hip 48° (tighter than the approximate provider). Adjust the world-axis convention in the calib file if turn signs/zeroing look off (the board placement defines the world frame).

- [ ] **Step 7: Commit**

```bash
git add vision/threed/calibration.py scripts/calibrate_bay_cameras.py vision/tests/test_checkerboard_calibration.py
git commit -m "feat(vision/threed): CheckerboardCalibration + one-time bay-calibration script"
```

---

## Final verification

- [ ] **Run the full suite**

Run: `python -m pytest coach/ store/ metrics/ vision/ -q`
Expected: all PASS (existing + new). The vision pose tests may be slow (MediaPipe) — that's expected.

- [ ] **Confirm 2D path is untouched**

With no `calibration` passed and no `pose_3d` rows, every existing 2D metric and the AI-coach/Review behavior is unchanged; the 3D metric fns no-op. The 3D metrics only appear once a swing has `pose_3d_frame` rows (i.e. `process_video(..., calibration=...)` was used).

---

## Self-review notes (coverage vs spec)

- §3 prerequisites → Task 11 capture script + the deferred note at the top.
- §4 scope (turn, X-factor + stretch, 3D side-bend; augment not replace) → Tasks 7, 8 (same names + `triangulated_3d`; 2D untouched).
- §5 synced-composite (shared frame index) → Tasks 4, 9 (index-aligned reconstruction).
- §6 pluggable calibration → Task 3 (AssumedGeometry) + Task 11 (Checkerboard).
- §7 architecture / modules → Tasks 2–10 map 1:1 to the module table.
- §8 angle math → Task 5 (`geometry3d`) + Tasks 7, 8.
- §10 store change (`pose_3d_frame`) → Task 1.
- §11 integration (MetricContext + coach + golftec_reference) → Tasks 6, 9, 10.
- §12 three-layer tests → synthetic (Tasks 4–8), `smooth_swing.mov` (Task 10 script), GolfTEC tolerance (Task 10 + 11 step 6).
- §13 risks → confidence tags (`confidence=medium/high` in method), visibility-gating (Task 4), no-op-without-3D (Tasks 7, 8).
