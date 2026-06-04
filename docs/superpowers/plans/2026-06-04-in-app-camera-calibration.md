# In-App Two-Camera Calibration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Self-service two-camera calibration inside the app — a Connect-screen card that captures a checkerboard live (MJPEG preview + coverage map), runs stereo calibration, and saves the active `bay_calib.json` the 3D pipeline uses.

**Architecture:** First live `FrameSource` (`LiveCameraSource`) → a pure checkerboard engine (`vision/threed/checkerboard.py`: detect → coverage → `cv2.stereoCalibrate`) → a threaded `CalibrationSupervisor` (mirrors the existing `CaptureSupervisor`, with an injectable camera-source factory for tests) → a `calibration` store table → `/api/calibration/*` (MJPEG preview + SSE status) → a Connect-screen card. The active calibration feeds `CheckerboardCalibration` (completing deferred Task 11) into `process_video`.

**Tech Stack:** Python 3.12, OpenCV (`cv2.findChessboardCorners`, `cv2.stereoCalibrate`), NumPy, FastAPI (`StreamingResponse` for SSE + MJPEG), sqlite store, React + TypeScript + Tailwind (Vite), pytest + vitest.

**Spec:** `docs/superpowers/specs/2026-06-04-in-app-camera-calibration-design.md`

> **ENVIRONMENT:** Python 3.12 at `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe` (NOT on PATH — use the full path). Node at `C:\Program Files\nodejs`. Frontend in `web/frontend` (`npm test`, `npm run build`). Build on `main` (user consented). Validate live parts later with the user's laptop webcam (single-camera test mode).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `vision/frames.py` | add `LiveCameraSource` (first live source) | 1 |
| `vision/threed/checkerboard.py` | `detect_board`, `coverage_cell`, `stereo_calibrate` + `bay_calib.json` dict | 2 |
| `vision/threed/calibration.py` | add `CheckerboardCalibration` + `active_calibration(conn)` (completes Task 11) | 3 |
| `scripts/calibrate_bay_cameras.py` | thin CLI over the engine | 3 |
| `store/schema.sql`, `store/repo.py`, `store/models.py` | `calibration` table + `Calibration` model + repo fns | 4 |
| `web/backend/calibration.py` | `CalibrationEventBus` + `CalibrationSupervisor` | 5 |
| `web/backend/deps.py` | `calibration_bus` + `get_calibration_supervisor` singletons | 6 |
| `web/backend/api_calibration.py`, `web/backend/app.py` | `/api/calibration/*` (MJPEG + SSE) + router register | 7 |
| `web/frontend/src/lib/{types,api}.ts`, `useCalibrationSse.ts` | typed calls + dedicated SSE hook | 8 |
| `web/frontend/src/pages/ConnectScreen.tsx`, `components/CalibrationCard.tsx` | the card | 9 |
| `vision/pipeline.py`, the guide | use active calibration; guide addendum + webcam smoke test | 10 |

---

## Task 1: `LiveCameraSource`

**Files:**
- Modify: `vision/frames.py`
- Test: `vision/tests/test_live_source.py`

**Context:** `vision/frames.py` has the `FrameSource` ABC (`frames()` → `FrameSample`, `.width/.height/.fps`, `close()`) and `split_views(frame, split)`. Add a live source over a capture device, with an **injectable capture factory** so tests pass a fake (no real webcam). It also exposes `read_composite()` (the raw full frame) — calibration needs both halves with pixel corners, not the split crops.

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_live_source.py
import numpy as np
from vision.frames import LiveCameraSource
from vision import constants as C


class _FakeCap:
    """Stand-in for cv2.VideoCapture: yields `n` synthetic BGR frames."""
    def __init__(self, n=3, w=640, h=480):
        self._n, self._i, self._w, self._h = n, 0, w, h
    def isOpened(self): return True
    def get(self, prop):
        import cv2
        return {cv2.CAP_PROP_FRAME_WIDTH: self._w,
                cv2.CAP_PROP_FRAME_HEIGHT: self._h,
                cv2.CAP_PROP_FPS: 30.0}.get(prop, 0)
    def read(self):
        if self._i >= self._n:
            return False, None
        self._i += 1
        return True, np.full((self._h, self._w, 3), self._i, dtype=np.uint8)
    def release(self): pass


def test_live_source_yields_split_frames():
    src = LiveCameraSource(device_index=0, max_frames=3,
                           cap_factory=lambda i: _FakeCap(n=3))
    assert src.width == 640 and src.height == 480 and src.fps == 30.0
    samples = list(src.frames())
    assert len(samples) == 3
    s = samples[0]
    assert C.VIEW_DOWN_LINE in s.view_crops and C.VIEW_FACE_ON in s.view_crops
    # each half is ~ half width
    assert s.view_crops[C.VIEW_FACE_ON].shape[1] == 320
    src.close()


def test_read_composite_returns_full_frame():
    src = LiveCameraSource(device_index=0, cap_factory=lambda i: _FakeCap(n=1))
    frame = src.read_composite()
    assert frame is not None and frame.shape == (480, 640, 3)
    assert src.read_composite() is None     # exhausted
    src.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_live_source.py -v`
Expected: FAIL — `cannot import name 'LiveCameraSource'`.

- [ ] **Step 3: Implement `LiveCameraSource`**

Append to `vision/frames.py` (after `VideoFileSource`):

```python
class LiveCameraSource(FrameSource):
    """Live capture device (the bay's synced side-by-side composite as a video
    device). First live FrameSource; foundation for live swing capture too.
    `cap_factory` is injectable so tests pass a fake (no real device opened)."""

    def __init__(self, device_index: int = 0, split: float = C.DEFAULT_SPLIT,
                 max_frames=None, cap_factory=None):
        self.device_index = device_index
        self.split = split
        self._max = max_frames
        factory = cap_factory or (lambda i: cv2.VideoCapture(i))
        self._cap = factory(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera device {device_index}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0

    def frames(self) -> Iterator[FrameSample]:
        i = 0
        while self._max is None or i < self._max:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield FrameSample(index=i, time_s=i / self.fps,
                              view_crops=split_views(frame, self.split))
            i += 1

    def read_composite(self):
        """Return the next raw composite frame (full, unsplit), or None."""
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_live_source.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add vision/frames.py vision/tests/test_live_source.py
git commit -m "feat(vision): LiveCameraSource (first live FrameSource)"
```

---

## Task 2: Checkerboard engine (`vision/threed/checkerboard.py`)

**Files:**
- Create: `vision/threed/checkerboard.py`
- Test: `vision/tests/test_checkerboard.py`

**Context:** Pure OpenCV, no web/device. `detect_board` finds the board in each half; `coverage_cell` buckets the board center into a grid; `stereo_calibrate` runs the calibration and returns the `bay_calib.json` dict + reprojection error. `stereo_calibrate` is tested with **synthetic corner correspondences** (project a known grid through two known cameras — no image needed), which proves the calibration math deterministically. `detect_board` is tested on a rendered checkerboard image.

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_checkerboard.py
import cv2
import numpy as np
from vision.threed import checkerboard as cb


def _render_checkerboard(cols, rows, square=40, border=40):
    """Render a (cols+1)x(rows+1)-square board -> cols x rows inner corners."""
    w = (cols + 1) * square + 2 * border
    h = (rows + 1) * square + 2 * border
    img = np.full((h, w), 255, np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                y0, x0 = border + r * square, border + c * square
                img[y0:y0 + square, x0:x0 + square] = 0
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_detect_board_finds_corners_in_both_halves():
    half = _render_checkerboard(9, 6)
    composite = np.hstack([half, half])        # left=DL, right=FO, same board
    det = cb.detect_board(composite, cols=9, rows=6, split=0.5)
    assert det.found_both
    assert det.fo_corners.shape[0] == 9 * 6 and det.dl_corners.shape[0] == 9 * 6
    assert det.fo_center is not None and det.dl_center is not None


def test_coverage_cell_buckets_position():
    assert cb.coverage_cell((10, 10), (400, 300), grid=(4, 3)) == (0, 0)
    assert cb.coverage_cell((399, 299), (400, 300), grid=(4, 3)) == (3, 2)


def test_stereo_calibrate_recovers_known_geometry():
    cols, rows, square_m = 9, 6, 0.025
    # object points (board plane), grid of cols*rows inner corners in meters
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_m
    K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], float)
    # two camera views of the board at a few placements
    fo_pts, dl_pts, obj_list = [], [], []
    rng_rots = [(-0.2, 0.1, 0.0), (0.1, -0.15, 0.05), (0.0, 0.2, -0.1),
                (0.15, 0.1, 0.1), (-0.1, -0.1, 0.0), (0.05, 0.05, -0.05)]
    for rot in rng_rots:
        rvec = np.array(rot, float)
        tvec_fo = np.array([-0.1, -0.08, 0.6], float)
        tvec_dl = np.array([-0.1, -0.08, 0.6], float)
        # DL camera rotated 30 deg about Y relative to FO -> different projection
        R_rel, _ = cv2.Rodrigues(np.array([0, 0.5236, 0], float))
        fo, _ = cv2.projectPoints(objp, rvec, tvec_fo, K, None)
        Rb, _ = cv2.Rodrigues(rvec)
        objp_cam = (R_rel @ (Rb @ objp.T + tvec_fo.reshape(3, 1)))
        dl, _ = cv2.projectPoints(objp_cam.T.astype(np.float32),
                                  np.zeros(3), np.zeros(3), K, None)
        fo_pts.append(fo.reshape(-1, 1, 2).astype(np.float32))
        dl_pts.append(dl.reshape(-1, 1, 2).astype(np.float32))
        obj_list.append(objp.copy())
    res = cb.stereo_calibrate(obj_list, fo_pts, dl_pts, image_size=(640, 480),
                              square_m=square_m, K_fo=K, K_dl=K)
    assert res.reprojection_error < 1.0          # px
    R_rel_out = np.array(res.calib["R_down_line"])
    rvec_out, _ = cv2.Rodrigues(R_rel_out)
    assert abs(abs(rvec_out[1, 0]) - 0.5236) < 0.05   # ~30 deg about Y recovered
    assert "image_width" in res.calib and res.calib["image_width"] == 640
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_checkerboard.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement the engine**

```python
# vision/threed/checkerboard.py
"""Pure checkerboard calibration engine (no web, no device).

detect_board: find the board in each half of a composite frame.
coverage_cell: bucket the board center into a grid (drives the coverage map).
stereo_calibrate: cv2.stereoCalibrate over accumulated corner pairs -> the
bay_calib.json dict + reprojection error.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

IN_TO_M = 0.0254
_CRIT = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


@dataclass
class BoardDetection:
    found_both: bool
    fo_corners: Optional[np.ndarray]   # (N,1,2) float32 in FO-half pixels
    dl_corners: Optional[np.ndarray]
    fo_center: Optional[Tuple[float, float]]
    dl_center: Optional[Tuple[float, float]]


@dataclass
class CalibrationResult:
    calib: dict                # the bay_calib.json dict
    reprojection_error: float
    n_poses: int


def _split(composite, split):
    w = composite.shape[1]
    x = int(round(w * split))
    return composite[:, x:], composite[:, :x]   # (face_on=right, down_line=left)


def _find(gray, cols, rows):
    ok, corners = cv2.findChessboardCorners(
        gray, (cols, rows),
        flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None, None
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), _CRIT)
    center = (float(corners[:, 0, 0].mean()), float(corners[:, 0, 1].mean()))
    return corners, center


def detect_board(composite, cols, rows, split=0.5) -> BoardDetection:
    fo, dl = _split(composite, split)
    g_fo = cv2.cvtColor(fo, cv2.COLOR_BGR2GRAY)
    g_dl = cv2.cvtColor(dl, cv2.COLOR_BGR2GRAY)
    fo_c, fo_ctr = _find(g_fo, cols, rows)
    dl_c, dl_ctr = _find(g_dl, cols, rows)
    return BoardDetection(found_both=(fo_c is not None and dl_c is not None),
                          fo_corners=fo_c, dl_corners=dl_c,
                          fo_center=fo_ctr, dl_center=dl_ctr)


def coverage_cell(center, image_size, grid=(4, 3)):
    """Grid cell (col,row) the board center falls in. image_size=(w,h)."""
    w, h = image_size
    gx, gy = grid
    cx = min(gx - 1, max(0, int(center[0] / max(w, 1) * gx)))
    cy = min(gy - 1, max(0, int(center[1] / max(h, 1) * gy)))
    return (cx, cy)


def _object_points(cols, rows, square_m):
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_m
    return objp


def stereo_calibrate(object_points, fo_pts, dl_pts, image_size, square_m,
                     K_fo=None, K_dl=None) -> CalibrationResult:
    """Calibrate from accumulated corner pairs. If K_* are None, intrinsics are
    estimated per view first, then fixed for the stereo solve. Face-on is the
    world reference (R=I, t=0); down_line carries the relative [R|T]."""
    w, h = image_size
    if K_fo is None:
        _, K_fo, d_fo, _, _ = cv2.calibrateCamera(object_points, fo_pts, (w, h), None, None)
    else:
        d_fo = np.zeros(5)
    if K_dl is None:
        _, K_dl, d_dl, _, _ = cv2.calibrateCamera(object_points, dl_pts, (w, h), None, None)
    else:
        d_dl = np.zeros(5)
    err, K_fo, d_fo, K_dl, d_dl, R, T, _, _ = cv2.stereoCalibrate(
        object_points, fo_pts, dl_pts, K_fo, d_fo, K_dl, d_dl, (w, h),
        flags=cv2.CALIB_FIX_INTRINSIC, criteria=_CRIT)
    calib = {
        "image_width": int(w), "image_height": int(h),
        "K_face_on": K_fo.tolist(), "K_down_line": K_dl.tolist(),
        "R_face_on": np.eye(3).tolist(), "t_face_on": [0.0, 0.0, 0.0],
        "R_down_line": R.tolist(), "t_down_line": T.ravel().tolist(),
        # world axes in the face-on camera frame (board defines target line/ground);
        # flip a sign here if turn reads reversed (see the calibration guide).
        "up": [0, -1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }
    return CalibrationResult(calib=calib, reprojection_error=float(err),
                             n_poses=len(object_points))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_checkerboard.py -v`
Expected: PASS. (If `test_detect_board...` is flaky, increase `square`/`border` in `_render_checkerboard` — a cleaner render detects more reliably; do NOT change the asserted corner counts.)

- [ ] **Step 5: Commit**

```bash
git add vision/threed/checkerboard.py vision/tests/test_checkerboard.py
git commit -m "feat(vision/threed): checkerboard calibration engine"
```

---

## Task 3: `CheckerboardCalibration` provider + `active_calibration` + CLI

**Files:**
- Modify: `vision/threed/calibration.py`
- Modify: `scripts/calibrate_bay_cameras.py` (thin CLI over the engine)
- Test: `vision/tests/test_checkerboard_calibration.py`

**Context:** This is the deferred 3D-plan Task 11, built here. The provider loads a `bay_calib.json` dict (same shape `stereo_calibrate` emits) and exposes the `Calibration` interface (`projection_matrices()`, `world_frame()`) so `reconstruct` works unchanged. `active_calibration(conn)` returns the right provider (checkerboard if an active row exists, else `AssumedGeometry`).

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_checkerboard_calibration.py
import numpy as np
from vision.threed.calibration import CheckerboardCalibration


def _calib():
    return {
        "image_width": 640, "image_height": 480,
        "K_face_on": [[800, 0, 320], [0, 800, 240], [0, 0, 1]],
        "K_down_line": [[800, 0, 320], [0, 800, 240], [0, 0, 1]],
        "R_face_on": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "t_face_on": [0, 0, 0],
        "R_down_line": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]], "t_down_line": [0, 0, 0.5],
        "up": [0, -1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }


def test_provider_from_dict_projects():
    cal = CheckerboardCalibration.from_dict(_calib())
    P_fo, P_dl = cal.projection_matrices()
    assert P_fo.shape == (3, 4) and P_dl.shape == (3, 4)
    assert cal.confidence == "high"
    assert np.allclose(cal.world_frame()["target_line"], [1, 0, 0])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_checkerboard_calibration.py -v`
Expected: FAIL — `cannot import name 'CheckerboardCalibration'`.

- [ ] **Step 3: Implement the provider + helper**

Append to `vision/threed/calibration.py` (the file already has `Calibration`, `_projection`, `_intrinsics`, `AssumedGeometryCalibration`):

```python
import json as _json


class CheckerboardCalibration(Calibration):
    """Loads a stereo calibration (from the in-app calibration or the CLI).
    HIGH confidence."""
    confidence = "high"

    def __init__(self, calib: dict):
        self._c = calib
        self.K_fo = np.array(calib["K_face_on"], float)
        self.K_dl = np.array(calib["K_down_line"], float)
        self.R_fo = np.array(calib["R_face_on"], float)
        self.t_fo = np.array(calib["t_face_on"], float)
        self.R_dl = np.array(calib["R_down_line"], float)
        self.t_dl = np.array(calib["t_down_line"], float)

    @classmethod
    def from_dict(cls, calib: dict):
        return cls(calib)

    @classmethod
    def from_file(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return cls(_json.load(f))

    def projection_matrices(self):
        return (_projection(self.K_fo, self.R_fo, self.t_fo),
                _projection(self.K_dl, self.R_dl, self.t_dl))

    def world_frame(self):
        return {"origin": np.array([0.0, 0.0, 0.0]),
                "up": np.array(self._c["up"], float),
                "target_line": np.array(self._c["target_line"], float),
                "depth": np.array(self._c["depth"], float)}


def active_calibration(conn, image_width=None, image_height=None, height_in=70.0):
    """Return CheckerboardCalibration for the active stored calibration, or an
    AssumedGeometryCalibration fallback (needs image dims for the fallback)."""
    from store import repo
    row = repo.get_active_calibration(conn)
    if row is not None:
        import json
        return CheckerboardCalibration.from_dict(json.loads(row.calib_json))
    if image_width and image_height:
        return AssumedGeometryCalibration(image_width, image_height, height_in)
    return None
```

- [ ] **Step 4: Rewrite `scripts/calibrate_bay_cameras.py` as a thin CLI**

Replace its body so it uses the engine (no duplicated math):

```python
# scripts/calibrate_bay_cameras.py
"""ONE-TIME CLI bay calibration (the in-app Connect card is the normal path).
Reads composite PNGs, detects the board, runs the engine, writes bay_calib.json.

Usage: python scripts/calibrate_bay_cameras.py <frames_dir> --cols 9 --rows 6 \
         --square-mm 25 --split 0.5 --out bay_calib.json
"""
import argparse, glob, json, os
import cv2
from vision.threed import checkerboard as cb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--cols", type=int, default=9)
    ap.add_argument("--rows", type=int, default=6)
    ap.add_argument("--square-mm", type=float, default=25.0)
    ap.add_argument("--split", type=float, default=0.5)
    ap.add_argument("--out", default="bay_calib.json")
    a = ap.parse_args()

    objp = cb._object_points(a.cols, a.rows, a.square_mm / 1000.0)
    obj_list, fo_pts, dl_pts, size = [], [], [], None
    for path in sorted(glob.glob(os.path.join(a.frames_dir, "*.png"))):
        img = cv2.imread(path)
        det = cb.detect_board(img, a.cols, a.rows, a.split)
        if det.found_both:
            obj_list.append(objp.copy())
            fo_pts.append(det.fo_corners); dl_pts.append(det.dl_corners)
            half_w = int(img.shape[1] * (1 - a.split))
            size = (half_w, img.shape[0])
    if len(obj_list) < 8:
        raise SystemExit(f"only {len(obj_list)} usable pairs; need >= 8")
    res = cb.stereo_calibrate(obj_list, fo_pts, dl_pts, size, a.square_mm / 1000.0)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res.calib, f, indent=2)
    print(f"wrote {a.out} from {res.n_poses} pairs, reproj err {res.reprojection_error:.3f}px")


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_checkerboard_calibration.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add vision/threed/calibration.py scripts/calibrate_bay_cameras.py vision/tests/test_checkerboard_calibration.py
git commit -m "feat(vision/threed): CheckerboardCalibration + active_calibration + CLI (Task 11)"
```

---

## Task 4: `calibration` store table + model + repo

**Files:**
- Modify: `store/models.py` (add `Calibration`)
- Modify: `store/schema.sql` (add table)
- Modify: `store/repo.py` (add fns)
- Test: `store/tests/test_calibration.py`

- [ ] **Step 1: Write the failing test**

```python
# store/tests/test_calibration.py   (uses the `db` fixture from conftest.py)
from store import repo


def test_save_activate_and_get_active(db):
    c1 = repo.save_calibration(db, device_index=0, cols=9, rows=6,
                               square_mm=25.0, n_poses=22, reprojection_error=0.41,
                               calib_json='{"image_width": 640}')
    assert repo.get_active_calibration(db).id == c1.id        # newest is active
    c2 = repo.save_calibration(db, device_index=0, cols=9, rows=6,
                               square_mm=25.0, n_poses=30, reprojection_error=0.3,
                               calib_json='{"image_width": 641}')
    assert repo.get_active_calibration(db).id == c2.id        # newest active now
    assert len(repo.list_calibrations(db)) == 2
    repo.set_active_calibration(db, c1.id)                    # re-activate older
    active = repo.get_active_calibration(db)
    assert active.id == c1.id and active.is_active == 1


def test_get_active_none_when_empty(db):
    assert repo.get_active_calibration(db) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest store/tests/test_calibration.py -v`
Expected: FAIL — `module 'store.repo' has no attribute 'save_calibration'`.

- [ ] **Step 3: Add the model**

In `store/models.py`, add:

```python
@dataclass
class Calibration:
    device_index: int
    cols: int
    rows: int
    square_mm: float
    n_poses: int
    reprojection_error: float
    calib_json: str
    is_active: int = 1
    created_at: Optional[str] = None
    id: Optional[int] = None
```

- [ ] **Step 4: Add the table**

In `store/schema.sql`, after `pose_3d_frame`:

```sql
CREATE TABLE IF NOT EXISTS calibration (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  device_index INTEGER NOT NULL,
  cols INTEGER NOT NULL, rows INTEGER NOT NULL, square_mm REAL NOT NULL,
  n_poses INTEGER NOT NULL, reprojection_error REAL NOT NULL,
  calib_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0
);
```

- [ ] **Step 5: Add repo fns**

In `store/repo.py` add (import `Calibration` into the existing models import):

```python
def _row_to_calibration(r):
    return Calibration(id=r["id"], created_at=r["created_at"],
                       device_index=r["device_index"], cols=r["cols"],
                       rows=r["rows"], square_mm=r["square_mm"],
                       n_poses=r["n_poses"], reprojection_error=r["reprojection_error"],
                       calib_json=r["calib_json"], is_active=r["is_active"])


def save_calibration(conn, *, device_index, cols, rows, square_mm, n_poses,
                     reprojection_error, calib_json):
    """Insert a calibration and make it the active one (clears other actives)."""
    conn.execute("UPDATE calibration SET is_active=0")
    cur = conn.execute(
        "INSERT INTO calibration(created_at, device_index, cols, rows, square_mm,"
        " n_poses, reprojection_error, calib_json, is_active) "
        "VALUES (?,?,?,?,?,?,?,?,1)",
        (dbmod.now_iso(), device_index, cols, rows, square_mm, n_poses,
         reprojection_error, calib_json))
    conn.commit()
    return get_calibration(conn, cur.lastrowid)


def get_calibration(conn, cal_id):
    r = conn.execute("SELECT * FROM calibration WHERE id=?", (cal_id,)).fetchone()
    return _row_to_calibration(r) if r else None


def get_active_calibration(conn):
    r = conn.execute("SELECT * FROM calibration WHERE is_active=1 "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    return _row_to_calibration(r) if r else None


def list_calibrations(conn):
    rows = conn.execute("SELECT * FROM calibration ORDER BY id DESC").fetchall()
    return [_row_to_calibration(r) for r in rows]


def set_active_calibration(conn, cal_id):
    conn.execute("UPDATE calibration SET is_active=0")
    conn.execute("UPDATE calibration SET is_active=1 WHERE id=?", (cal_id,))
    conn.commit()
    return get_calibration(conn, cal_id)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest store/tests/test_calibration.py store/ -q`
Expected: PASS (new + no store regressions).

- [ ] **Step 7: Commit**

```bash
git add store/models.py store/schema.sql store/repo.py store/tests/test_calibration.py
git commit -m "feat(store): calibration table + repo (save/active/list)"
```

---

## Task 5: `CalibrationSupervisor`

**Files:**
- Create: `web/backend/calibration.py`
- Test: `web/backend/tests/test_calibration_supervisor.py`

**Context:** Mirrors `CaptureSupervisor` (`web/backend/capture.py`): a thread-safe event bus + a supervisor whose **testable core** (`process_frame`) has no thread/device. An injectable `source_factory` lets tests pass a fake camera. Capture accumulates good, *new-coverage* poses (debounced so a held-still board isn't double-counted), tracks coverage, keeps the latest overlay JPEG for MJPEG, and publishes status. `run()` calibrates the accumulated poses and persists.

- [ ] **Step 1: Write the failing test**

```python
# web/backend/tests/test_calibration_supervisor.py
import numpy as np
from store import db as dbmod, repo
from web.backend.calibration import CalibrationEventBus, CalibrationSupervisor
from vision.threed.checkerboard import BoardDetection


def _conn():
    c = dbmod.connect(":memory:"); dbmod.init_db(conn=c); return c


def _det(found, cx=100, cy=100):
    n = 54
    corners = np.zeros((n, 1, 2), np.float32)
    return BoardDetection(found_both=found, fo_corners=corners, dl_corners=corners,
                          fo_center=(cx, cy), dl_center=(cx, cy))


def test_process_frame_accumulates_new_coverage_only(monkeypatch):
    conn = _conn(); bus = CalibrationEventBus()
    sup = CalibrationSupervisor(conn=conn, bus=bus)
    # configure() sets params WITHOUT spawning the capture thread, so we drive
    # process_frame deterministically (no background thread racing the count).
    sup.configure(device_index=0, cols=9, rows=6, square_mm=25.0)
    # same position twice -> 1 pose; new cell -> 2
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 100, 100))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == 1
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 600, 400))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == 2


def test_run_calibrates_and_persists(monkeypatch):
    conn = _conn(); bus = CalibrationEventBus()
    sup = CalibrationSupervisor(conn=conn, bus=bus)
    sup.configure(device_index=0, cols=9, rows=6, square_mm=25.0)
    # stub the engine so the test is deterministic
    from vision.threed.checkerboard import CalibrationResult
    monkeypatch.setattr("web.backend.calibration.stereo_calibrate",
                        lambda *a, **k: CalibrationResult(
                            calib={"image_width": 640}, reprojection_error=0.4, n_poses=10))
    # seed 10 accumulated poses (each a new coverage cell)
    for i in range(10):
        monkeypatch.setattr("web.backend.calibration.detect_board",
                            lambda *a, _i=i, **k: _det(True, 30 + _i * 55, 30 + _i * 25))
        sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    result = sup.run()
    assert result["ok"] is True and result["n_poses"] >= 8
    assert repo.get_active_calibration(conn) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_calibration_supervisor.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement**

```python
# web/backend/calibration.py
"""In-app camera calibration engine (mirrors CaptureSupervisor).

CalibrationEventBus: thread-safe event buffer (publish from the capture thread;
SSE coroutine drains). CalibrationSupervisor: owns a LiveCameraSource, detects
the board per frame, accumulates new-coverage good poses, keeps an overlay JPEG
for MJPEG, and run() stereo-calibrates + persists. process_frame() is the
thread-free testable core.
"""
import threading
from typing import Callable, Optional

import cv2
import numpy as np

from store import repo
from vision.frames import LiveCameraSource
from vision.threed.checkerboard import (
    detect_board, coverage_cell, stereo_calibrate, _object_points)


class CalibrationEventBus:
    def __init__(self):
        self._lock = threading.Lock(); self._events = []
    def publish(self, event, data):
        with self._lock: self._events.append({"event": event, "data": data})
    def drain(self):
        with self._lock:
            out = self._events; self._events = []; return out


def _default_source_factory(device_index, split):
    return LiveCameraSource(device_index=device_index, split=split)


class CalibrationSupervisor:
    def __init__(self, *, conn, bus, source_factory: Callable = _default_source_factory):
        self.conn = conn
        self.bus = bus
        self._source_factory = source_factory
        self._lock = threading.Lock()
        self._run = False
        self._thread = None
        self._source = None
        self._reset_state()

    def _reset_state(self):
        self.cols = self.rows = 0
        self.square_mm = 25.0
        self.device_index = 0
        self.split = 0.5
        self.image_size = None
        self._obj, self._fo, self._dl = [], [], []
        self._covered = set()
        self._overlay_jpeg = None
        self._capturing = False

    # ---- testable core (no thread/device) --------------------------------
    def process_frame(self, composite) -> bool:
        det = detect_board(composite, self.cols, self.rows, self.split)
        h, w = composite.shape[:2]
        half = (int(w * (1 - self.split)), h)
        self.image_size = half
        accepted = False
        if det.found_both:
            cell = coverage_cell(det.fo_center, half)
            if cell not in self._covered:
                self._covered.add(cell)
                self._obj.append(_object_points(self.cols, self.rows, self.square_mm / 1000.0))
                self._fo.append(det.fo_corners)
                self._dl.append(det.dl_corners)
                accepted = True
        self._overlay_jpeg = self._render_overlay(composite, det)
        self.bus.publish("calibration_status", self.status())
        return accepted

    def _render_overlay(self, composite, det):
        img = composite.copy()
        if det.found_both:
            x0 = int(img.shape[1] * (1 - self.split))
            cv2.drawChessboardCorners(img[:, x0:], (self.cols, self.rows),
                                      det.fo_corners, True)
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes() if ok else None

    def latest_overlay_jpeg(self):
        return self._overlay_jpeg

    def status(self):
        return {"capturing": self._capturing, "good_poses": len(self._obj),
                "coverage": sorted(list(self._covered)),
                "device_index": self.device_index,
                "cols": self.cols, "rows": self.rows}

    # ---- start/stop/run ---------------------------------------------------
    def configure(self, *, device_index, cols, rows, square_mm):
        """Set params + clear accumulation WITHOUT opening a device or spawning
        the capture thread. The thread-free path used by tests and by start()."""
        self._reset_state()
        self.device_index, self.cols, self.rows = device_index, cols, rows
        self.square_mm = square_mm

    def start(self, *, device_index, cols, rows, square_mm, source_factory=None):
        with self._lock:
            if self._run:
                return
            self.configure(device_index=device_index, cols=cols, rows=rows,
                           square_mm=square_mm)
            self._source = (source_factory or self._source_factory)(device_index, self.split)
            self._capturing = True
            self._run = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        import time
        while self._run:
            frame = self._source.read_composite() if self._source else None
            if frame is None:
                time.sleep(0.03); continue
            try:
                self.process_frame(frame)
            except Exception:
                pass

    def stop(self):
        with self._lock:
            self._run = False
            self._capturing = False
        if self._source is not None:
            try: self._source.close()
            except Exception: pass
            self._source = None

    def run(self):
        if len(self._obj) < 8:
            return {"ok": False, "error": f"only {len(self._obj)} poses; need >= 8",
                    "n_poses": len(self._obj)}
        size = self.image_size or (640, 480)
        res = stereo_calibrate(self._obj, self._fo, self._dl, size,
                               self.square_mm / 1000.0)
        import json
        repo.save_calibration(
            self.conn, device_index=self.device_index, cols=self.cols,
            rows=self.rows, square_mm=self.square_mm, n_poses=res.n_poses,
            reprojection_error=res.reprojection_error,
            calib_json=json.dumps(res.calib))
        self.bus.publish("calibration_done",
                         {"n_poses": res.n_poses,
                          "reprojection_error": res.reprojection_error})
        return {"ok": True, "n_poses": res.n_poses,
                "reprojection_error": res.reprojection_error}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_calibration_supervisor.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add web/backend/calibration.py web/backend/tests/test_calibration_supervisor.py
git commit -m "feat(web): CalibrationSupervisor (capture + detect + run)"
```

---

## Task 6: deps singletons

**Files:**
- Modify: `web/backend/deps.py`
- Test: `web/backend/tests/test_calibration_deps.py`

- [ ] **Step 1: Write the failing test**

```python
# web/backend/tests/test_calibration_deps.py
from web.backend import deps


def test_calibration_singletons_and_reset():
    bus = deps.calibration_bus()
    assert deps.calibration_bus() is bus               # singleton
    sup = deps.get_calibration_supervisor()
    assert deps.get_calibration_supervisor() is sup
    deps.reset_calibration_singletons()
    assert deps.calibration_bus() is not bus
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_calibration_deps.py -v`
Expected: FAIL — `module 'web.backend.deps' has no attribute 'calibration_bus'`.

- [ ] **Step 3: Implement**

In `web/backend/deps.py`, add (reuse `_listener_conn` for a dedicated thread connection), and import the calibration classes at top:

```python
from web.backend.calibration import CalibrationEventBus, CalibrationSupervisor

_calibration_bus = None
_calibration_supervisor = None


def calibration_bus() -> CalibrationEventBus:
    global _calibration_bus
    if _calibration_bus is None:
        _calibration_bus = CalibrationEventBus()
    return _calibration_bus


def get_calibration_supervisor() -> CalibrationSupervisor:
    global _calibration_supervisor
    if _calibration_supervisor is None:
        _calibration_supervisor = CalibrationSupervisor(
            conn=_listener_conn(), bus=calibration_bus())
    return _calibration_supervisor


def reset_calibration_singletons():
    global _calibration_bus, _calibration_supervisor
    if _calibration_supervisor is not None:
        try: _calibration_supervisor.stop()
        except Exception: pass
    _calibration_bus = None
    _calibration_supervisor = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_calibration_deps.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/deps.py web/backend/tests/test_calibration_deps.py
git commit -m "feat(web): calibration deps singletons"
```

---

## Task 7: API (`/api/calibration/*`) incl. MJPEG + SSE

**Files:**
- Create: `web/backend/api_calibration.py`
- Modify: `web/backend/app.py` (register router)
- Test: `web/backend/tests/test_api_calibration.py`

**Context:** Mirrors `api_settings.py` (APIRouter, pydantic, `Depends`). The supervisor is injected via `get_calibration_supervisor`; tests override it with a fake. SSE + MJPEG use `StreamingResponse` (`text/event-stream` and `multipart/x-mixed-replace`).

- [ ] **Step 1: Write the failing test**

```python
# web/backend/tests/test_api_calibration.py
from fastapi.testclient import TestClient
from web.backend.app import create_app
from web.backend import deps


class _FakeSup:
    def __init__(self): self._poses = 0; self.started = None
    def start(self, **kw): self.started = kw
    def stop(self): pass
    def run(self): return {"ok": True, "n_poses": 12, "reprojection_error": 0.4}
    def status(self): return {"capturing": True, "good_poses": self._poses,
                              "coverage": [], "device_index": 0, "cols": 9, "rows": 6}
    def latest_overlay_jpeg(self): return b"\xff\xd8jpeg\xff\xd9"


def _client():
    app = create_app()
    fake = _FakeSup()
    app.dependency_overrides[deps.get_calibration_supervisor] = lambda: fake
    return TestClient(app), fake


def test_start_stop_run_status():
    client, fake = _client()
    r = client.post("/api/calibration/start",
                    json={"device_index": 0, "cols": 9, "rows": 6, "square_mm": 25.0})
    assert r.status_code == 200 and fake.started["cols"] == 9
    assert client.get("/api/calibration/status").json()["cols"] == 9
    assert client.post("/api/calibration/run").json()["ok"] is True
    assert client.post("/api/calibration/stop").status_code == 200


def test_preview_streams_jpeg():
    client, _ = _client()
    r = client.get("/api/calibration/preview", headers={"Range": "bytes=0-0"})
    assert r.status_code == 200
    assert "multipart/x-mixed-replace" in r.headers["content-type"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_api_calibration.py -v`
Expected: FAIL — 404 (router not registered).

- [ ] **Step 3: Implement the API**

```python
# web/backend/api_calibration.py
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from store import repo
from web.backend.deps import (get_conn, get_calibration_supervisor,
                              calibration_bus)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


class StartIn(BaseModel):
    device_index: int = 0
    cols: int = 9
    rows: int = 6
    square_mm: float = 25.0


@router.post("/start")
def start(body: StartIn, sup=Depends(get_calibration_supervisor)):
    sup.start(device_index=body.device_index, cols=body.cols, rows=body.rows,
              square_mm=body.square_mm)
    return {"ok": True}


@router.post("/stop")
def stop(sup=Depends(get_calibration_supervisor)):
    sup.stop(); return {"ok": True}


@router.post("/run")
def run(sup=Depends(get_calibration_supervisor)):
    return sup.run()


@router.get("/status")
def status(sup=Depends(get_calibration_supervisor)):
    return sup.status()


@router.get("/active")
def active(conn=Depends(get_conn)):
    c = repo.get_active_calibration(conn)
    if c is None:
        return None
    return {"id": c.id, "created_at": c.created_at, "n_poses": c.n_poses,
            "reprojection_error": c.reprojection_error,
            "cols": c.cols, "rows": c.rows, "device_index": c.device_index}


@router.get("/history")
def history(conn=Depends(get_conn)):
    return [{"id": c.id, "created_at": c.created_at, "n_poses": c.n_poses,
             "reprojection_error": c.reprojection_error, "is_active": c.is_active}
            for c in repo.list_calibrations(conn)]


@router.post("/activate/{cal_id}")
def activate(cal_id: int, conn=Depends(get_conn)):
    c = repo.set_active_calibration(conn, cal_id)
    return {"ok": c is not None}


@router.get("/export")
def export(conn=Depends(get_conn)):
    c = repo.get_active_calibration(conn)
    if c is None:
        return JSONResponse(status_code=404, content={"error": "no active calibration"})
    return JSONResponse(content=json.loads(c.calib_json),
                        headers={"Content-Disposition": "attachment; filename=bay_calib.json"})


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(request: Request, bus=Depends(calibration_bus)):
    async def gen():
        while True:
            if await request.is_disconnected():
                break
            for e in bus.drain():
                yield _sse(e["event"], e["data"])
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/preview")
def preview(sup=Depends(get_calibration_supervisor)):
    boundary = "frame"

    def gen():
        import time
        for _ in range(100000):                     # bounded; client disconnects end it
            jpeg = sup.latest_overlay_jpeg()
            if jpeg:
                yield (b"--" + boundary.encode() + b"\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            time.sleep(0.1)

    return StreamingResponse(
        gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")
```

- [ ] **Step 4: Register the router**

In `web/backend/app.py`, add the import and `app.include_router(api_calibration.router)` next to the others.

- [ ] **Step 5: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_api_calibration.py -v`
Expected: PASS. (For `test_preview_streams_jpeg`, `TestClient` returns once the first chunk is available; the `Range` header isn't required by the server — it's just to keep the test from hanging on the stream. If it hangs, wrap the GET in `with client.stream("GET", ...) as r:` and assert on `r.headers` then close.)

- [ ] **Step 6: Run the full backend suite**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/ -q`
Expected: PASS (no regressions).

- [ ] **Step 7: Commit**

```bash
git add web/backend/api_calibration.py web/backend/app.py web/backend/tests/test_api_calibration.py
git commit -m "feat(web): /api/calibration/* with MJPEG preview + SSE"
```

---

## Task 8: Frontend types + API + SSE hook

**Files:**
- Modify: `web/frontend/src/lib/types.ts`, `web/frontend/src/lib/api.ts`
- Create: `web/frontend/src/lib/useCalibrationSse.ts`
- Test: `web/frontend/src/lib/calibration.test.ts` (or the repo's existing vitest location)

**Context:** Match the existing `getJSON`/`postJSON` helpers in `api.ts` and the `useSse` pattern. The calibration SSE is a **dedicated** `EventSource("/api/calibration/stream")` (high-frequency, only open while the card is mounted).

- [ ] **Step 1: Write the failing test**

```typescript
// web/frontend/src/lib/calibration.test.ts
import { describe, it, expect, vi, beforeEach } from "vitest";
import { startCalibration, runCalibration, getCalibrationStatus } from "../api";

describe("calibration api", () => {
  beforeEach(() => {
    global.fetch = vi.fn(async (url: string, opts?: any) => ({
      ok: true, status: 200,
      json: async () => ({ url, body: opts?.body ? JSON.parse(opts.body) : null }),
    })) as any;
  });
  it("posts start with params", async () => {
    const r: any = await startCalibration({ device_index: 0, cols: 9, rows: 6, square_mm: 25 });
    expect(r.url).toBe("/api/calibration/start");
    expect(r.body.cols).toBe(9);
  });
  it("runs and reads status", async () => {
    expect((await runCalibration() as any).url).toBe("/api/calibration/run");
    expect((await getCalibrationStatus() as any).url).toBe("/api/calibration/status");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/frontend`): `& "C:\Program Files\nodejs\npm.cmd" test -- calibration`
Expected: FAIL — exports not found.

- [ ] **Step 3: Add types**

In `web/frontend/src/lib/types.ts` add:

```typescript
export interface CalibrationStartIn {
  device_index: number; cols: number; rows: number; square_mm: number;
}
export interface CalibrationStatus {
  capturing: boolean; good_poses: number; coverage: [number, number][];
  device_index: number; cols: number; rows: number;
}
export interface CalibrationResult {
  ok: boolean; n_poses?: number; reprojection_error?: number; error?: string;
}
export interface ActiveCalibration {
  id: number; created_at: string; n_poses: number;
  reprojection_error: number; cols: number; rows: number; device_index: number;
}
```

- [ ] **Step 4: Add API calls**

In `web/frontend/src/lib/api.ts` add (mirroring the existing helpers):

```typescript
import type {
  CalibrationStartIn, CalibrationStatus, CalibrationResult, ActiveCalibration,
} from "./types";

export const startCalibration = (b: CalibrationStartIn) =>
  postJSON<{ ok: boolean }>("/api/calibration/start", b);
export const stopCalibration = () => postJSON<{ ok: boolean }>("/api/calibration/stop", {});
export const runCalibration = () => postJSON<CalibrationResult>("/api/calibration/run", {});
export const getCalibrationStatus = () =>
  getJSON<CalibrationStatus>("/api/calibration/status");
export const getActiveCalibration = () =>
  getJSON<ActiveCalibration | null>("/api/calibration/active");
```

- [ ] **Step 5: Add the dedicated SSE hook**

```typescript
// web/frontend/src/lib/useCalibrationSse.ts
import { useEffect, useRef } from "react";

type Handlers = Record<string, (data: any) => void>;

/** Dedicated SSE for calibration; only open while `active` (card mounted). */
export function useCalibrationSse(active: boolean, handlers: Handlers) {
  const ref = useRef(handlers); ref.current = handlers;
  useEffect(() => {
    if (!active) return;
    const es = new EventSource("/api/calibration/stream");
    const names = ["calibration_status", "calibration_done"];
    const ls = names.map((n) => {
      const fn = (e: MessageEvent) => {
        try { ref.current[n]?.(JSON.parse(e.data)); } catch { /* ignore */ }
      };
      es.addEventListener(n, fn as EventListener);
      return [n, fn] as const;
    });
    return () => { ls.forEach(([n, fn]) => es.removeEventListener(n, fn as EventListener)); es.close(); };
  }, [active]);
}
```

- [ ] **Step 6: Run test to verify it passes**

Run (from `web/frontend`): `& "C:\Program Files\nodejs\npm.cmd" test -- calibration`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/lib/types.ts web/frontend/src/lib/api.ts web/frontend/src/lib/useCalibrationSse.ts web/frontend/src/lib/calibration.test.ts
git commit -m "feat(frontend): calibration types + api + SSE hook"
```

---

## Task 9: Connect-screen "Camera Calibration" card

**Files:**
- Create: `web/frontend/src/components/CalibrationCard.tsx`
- Modify: `web/frontend/src/pages/ConnectScreen.tsx` (render the card)
- Test: `web/frontend/src/components/CalibrationCard.test.tsx`

**Context:** A self-contained card using the project's Tailwind dark/green tokens (e.g. text `#E7EEE9`, muted `#8B978F`, primary green `#84CE39`). It holds inputs (device index, cols, rows, square size in inches/mm), the MJPEG `<img>` preview, a coverage-grid widget, the good-pose counter + hint, and the Start/Stop/Run/Export controls + result. It subscribes to `useCalibrationSse` while mounted.

- [ ] **Step 1: Write the failing test**

```tsx
// web/frontend/src/components/CalibrationCard.test.tsx
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { CalibrationCard } from "../CalibrationCard";

vi.mock("../../lib/api", () => ({
  startCalibration: vi.fn(async () => ({ ok: true })),
  stopCalibration: vi.fn(async () => ({ ok: true })),
  runCalibration: vi.fn(async () => ({ ok: true, n_poses: 12, reprojection_error: 0.4 })),
  getCalibrationStatus: vi.fn(async () => ({ capturing: false, good_poses: 0, coverage: [], device_index: 0, cols: 9, rows: 6 })),
  getActiveCalibration: vi.fn(async () => null),
}));
vi.mock("../../lib/useCalibrationSse", () => ({ useCalibrationSse: () => {} }));

describe("CalibrationCard", () => {
  beforeEach(() => vi.clearAllMocks());
  it("renders title and start button", async () => {
    render(<CalibrationCard />);
    expect(screen.getByText(/Camera Calibration/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Start/i })).toBeTruthy();
  });
  it("calls startCalibration on Start", async () => {
    const api = await import("../../lib/api");
    render(<CalibrationCard />);
    fireEvent.click(screen.getByRole("button", { name: /Start/i }));
    expect(api.startCalibration).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/frontend`): `& "C:\Program Files\nodejs\npm.cmd" test -- CalibrationCard`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the card**

```tsx
// web/frontend/src/components/CalibrationCard.tsx
import { useEffect, useState } from "react";
import {
  startCalibration, stopCalibration, runCalibration,
  getActiveCalibration,
} from "../lib/api";
import { useCalibrationSse } from "../lib/useCalibrationSse";
import type { CalibrationResult, ActiveCalibration } from "../lib/types";

export function CalibrationCard() {
  const [device, setDevice] = useState("0");
  const [cols, setCols] = useState("9");
  const [rows, setRows] = useState("6");
  const [squareIn, setSquareIn] = useState("1.0");      // inches; converted to mm
  const [capturing, setCapturing] = useState(false);
  const [goodPoses, setGoodPoses] = useState(0);
  const [coverage, setCoverage] = useState<[number, number][]>([]);
  const [result, setResult] = useState<CalibrationResult | null>(null);
  const [active, setActive] = useState<ActiveCalibration | null>(null);

  useEffect(() => { getActiveCalibration().then(setActive).catch(() => {}); }, []);

  useCalibrationSse(capturing, {
    calibration_status: (d) => { setGoodPoses(d.good_poses); setCoverage(d.coverage); },
    calibration_done: () => { getActiveCalibration().then(setActive).catch(() => {}); },
  });

  const onStart = () => {
    startCalibration({
      device_index: parseInt(device || "0", 10) || 0,
      cols: parseInt(cols || "9", 10) || 9,
      rows: parseInt(rows || "6", 10) || 6,
      square_mm: (parseFloat(squareIn || "1") || 1) * 25.4,
    }).then(() => setCapturing(true)).catch(() => {});
  };
  const onStop = () => { stopCalibration().finally(() => setCapturing(false)); };
  const onRun = () => { runCalibration().then(setResult).catch(() => {}); };

  const covered = new Set(coverage.map(([c, r]) => `${c},${r}`));
  const grid = [];
  for (let r = 0; r < 3; r++) for (let c = 0; c < 4; c++)
    grid.push(<div key={`${c},${r}`} className={
      "h-6 rounded " + (covered.has(`${c},${r}`) ? "bg-[#84CE39]" : "bg-[#1A211D]")} />);

  return (
    <div className="rounded-2xl bg-[#1A211D] p-6 space-y-4">
      <h2 className="text-xl font-semibold text-[#E7EEE9]">Camera Calibration</h2>
      <p className="text-sm text-[#8B978F]">
        Recalibrate the bay cameras if they’ve been moved. See the calibration guide
        for the checkerboard. Square size is in inches (converted automatically).
      </p>

      <div className="grid grid-cols-4 gap-3">
        <label className="text-xs text-[#8B978F]">Device
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={device} onChange={(e) => setDevice(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Inner cols
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={cols} onChange={(e) => setCols(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Inner rows
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={rows} onChange={(e) => setRows(e.target.value)} /></label>
        <label className="text-xs text-[#8B978F]">Square (in)
          <input className="mt-1 w-full bg-[#0A0D0B] rounded p-2 text-[#E7EEE9]"
                 value={squareIn} onChange={(e) => setSquareIn(e.target.value)} /></label>
      </div>

      {capturing && (
        <img alt="calibration preview" src="/api/calibration/preview"
             className="w-full rounded-lg border border-[#2A332C]" />
      )}

      <div className="flex items-center gap-4">
        <div className="grid grid-cols-4 gap-1 flex-1">{grid}</div>
        <div className="text-[#E7EEE9] text-sm whitespace-nowrap">
          {goodPoses} good pose{goodPoses === 1 ? "" : "s"}
        </div>
      </div>

      <div className="flex gap-3">
        {!capturing
          ? <button onClick={onStart}
              className="px-4 py-2 rounded-lg bg-[#84CE39] text-[#0A0D0B] font-medium">Start Capture</button>
          : <button onClick={onStop}
              className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Stop</button>}
        <button onClick={onRun} disabled={goodPoses < 8}
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9] disabled:opacity-40">
          Run Calibration</button>
        <a href="/api/calibration/export"
          className="px-4 py-2 rounded-lg bg-[#2A332C] text-[#E7EEE9]">Export</a>
      </div>

      {result && (
        <div className={"text-sm " + (result.ok ? "text-[#84CE39]" : "text-red-400")}>
          {result.ok
            ? `✓ Calibrated · ${result.n_poses} poses · reproj ${result.reprojection_error?.toFixed(2)}px`
            : `✗ ${result.error}`}
        </div>
      )}
      {active && (
        <div className="text-xs text-[#8B978F]">
          Active: #{active.id} · {active.n_poses} poses · {active.reprojection_error.toFixed(2)}px · {active.created_at}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Render it on the Connect screen**

In `web/frontend/src/pages/ConnectScreen.tsx`, import `CalibrationCard` and render `<CalibrationCard />` inside the page container (below the existing R50/settings content, within the `max-w-5xl` wrapper).

- [ ] **Step 5: Run test to verify it passes**

Run (from `web/frontend`): `& "C:\Program Files\nodejs\npm.cmd" test -- CalibrationCard`
Expected: PASS.

- [ ] **Step 6: Build the frontend**

Run (from `web/frontend`): `& "C:\Program Files\nodejs\npm.cmd" run build`
Expected: `tsc` + `vite build` succeed (no type errors).

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/components/CalibrationCard.tsx web/frontend/src/pages/ConnectScreen.tsx web/frontend/src/components/CalibrationCard.test.tsx
git commit -m "feat(frontend): Camera Calibration card on Connect screen"
```

---

## Task 10: Wire active calibration into the 3D pipeline + docs/webcam smoke test

**Files:**
- Modify: `vision/pipeline.py` (use the active calibration when `calibration` not given)
- Modify: `docs/guides/bay-camera-calibration-guide.md` (in-app addendum)
- Create: `scripts/webcam_calibration_smoketest.md` (manual webcam steps)
- Test: `vision/tests/test_pipeline_active_calib.py`

- [ ] **Step 1: Write the failing test**

```python
# vision/tests/test_pipeline_active_calib.py
from store import db as dbmod, repo
from vision.threed.calibration import active_calibration, CheckerboardCalibration


def test_active_calibration_prefers_stored_then_falls_back():
    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    # none stored -> AssumedGeometry fallback when dims given
    cal = active_calibration(conn, image_width=1214, image_height=1284)
    assert cal is not None and cal.__class__.__name__ == "AssumedGeometryCalibration"
    # store one -> CheckerboardCalibration returned
    repo.save_calibration(conn, device_index=0, cols=9, rows=6, square_mm=25.0,
                          n_poses=20, reprojection_error=0.4,
                          calib_json='{"image_width":640,"image_height":480,'
                          '"K_face_on":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"K_down_line":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"R_face_on":[[1,0,0],[0,1,0],[0,0,1]],"t_face_on":[0,0,0],'
                          '"R_down_line":[[1,0,0],[0,1,0],[0,0,1]],"t_down_line":[0,0,0.5],'
                          '"up":[0,-1,0],"target_line":[1,0,0],"depth":[0,0,1]}')
    cal2 = active_calibration(conn, image_width=1214, image_height=1284)
    assert isinstance(cal2, CheckerboardCalibration) and cal2.confidence == "high"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_pipeline_active_calib.py -v`
Expected: FAIL or ERROR until `active_calibration` resolves a stored row (it was added in Task 3; this test pins the precedence end-to-end with the real table from Task 4).

- [ ] **Step 3: Use the active calibration in `process_video` when none is passed**

In `vision/pipeline.py`, change the 3D block so that when `calibration is None` it still tries the active stored one:

```python
        if calibration is None:
            from vision.threed.calibration import active_calibration
            calibration = active_calibration(conn, image_width=source.width,
                                             image_height=source.height)
        if calibration is not None:
            frames_3d = reconstruct_window(
                face_on, down_line, calibration,
                window.start_index, window.end_index)
            if frames_3d:
                from store import repo
                repo.save_pose_3d_frames(conn, swing_id, frames_3d)
```

(`active_calibration` returns the stored `CheckerboardCalibration` if present, else an `AssumedGeometry` from the source dims — so 3D now happens automatically once a calibration exists, with no per-call argument.)

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest vision/tests/test_pipeline_active_calib.py -v`
Expected: PASS.

- [ ] **Step 5: Add the guide addendum + webcam smoke-test doc**

Append to `docs/guides/bay-camera-calibration-guide.md`:

```markdown
## In the app (the normal way)

You don't need the command line. In the app: **Connect → Camera Calibration →
Start Capture**, wave the board through the bay (watch the live preview + coverage
map fill in), then **Run Calibration**. It saves and activates automatically; the
3D metrics use it immediately. **Export** downloads `bay_calib.json` as a backup.
```

Create `scripts/webcam_calibration_smoketest.md`:

```markdown
# Webcam smoke test (single-camera, validates the live plumbing)

A laptop webcam is ONE camera, so it can't produce a real stereo calibration —
but it exercises the whole live flow (device I/O, board detection, MJPEG preview,
coverage map, SSE). Square size doesn't matter here (angles are scale-invariant).

1. Start the app: `python -m web.backend.seed_dev` then
   `python -m uvicorn web.backend.app:app --port 8000`; open http://localhost:8000.
2. Go to **Connect → Camera Calibration**. Set Device to your webcam index
   (usually `0`), cols/rows to your board's inner corners, square to its inches.
3. Click **Start Capture**. Hold the printed checkerboard in front of the webcam.
4. CONFIRM: the live preview shows, the detected corners get drawn on the board,
   the good-pose counter climbs as you move the board to new areas, and the
   coverage grid fills in. (A single camera means "both halves" are the same
   webcam view — detection/preview/coverage all still exercise.)
5. With 8+ poses, **Run Calibration** returns a result (the numbers are
   meaningless with one camera — that's expected; this only validates plumbing).
6. Report what you saw (preview live? corners drawn? counter climbing? coverage
   filling? run returned?).
```

- [ ] **Step 6: Run the full backend + vision-3D suite**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest store/ metrics/ coach/ web/backend/ vision/tests/test_live_source.py vision/tests/test_checkerboard.py vision/tests/test_checkerboard_calibration.py vision/tests/test_reconstruct.py vision/tests/test_pipeline_active_calib.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add vision/pipeline.py docs/guides/bay-camera-calibration-guide.md scripts/webcam_calibration_smoketest.md vision/tests/test_pipeline_active_calib.py
git commit -m "feat(vision): auto-use active calibration in pipeline + guide/webcam smoke test"
```

---

## Final verification

- [ ] Run the full backend + python suites: `... -m pytest store/ metrics/ coach/ web/backend/ vision/tests/test_live_source.py vision/tests/test_checkerboard*.py vision/tests/test_reconstruct.py vision/tests/test_pipeline_active_calib.py -q` → all PASS.
- [ ] Frontend: from `web/frontend`, `npm test` (vitest green) and `npm run build` (tsc + vite OK).
- [ ] Manual: follow `scripts/webcam_calibration_smoketest.md` with the user's webcam; confirm live preview, corner overlay, coverage map, pose counter, and run result.

---

## Self-review (coverage vs spec)

- §4 LiveCameraSource → Task 1. · §5 checkerboard engine → Task 2. · Task 11 CheckerboardCalibration → Task 3. · §7 calibration table → Task 4. · §6 CalibrationSupervisor → Task 5. · deps → Task 6. · §8 API (MJPEG + SSE) → Task 7. · §9 frontend card → Tasks 8–9. · §10 wire-up + guide + webcam test → Task 10. · §11 validation: synthetic (Task 2), mock supervisor (Task 5), API/store/frontend tests (Tasks 4,7,8,9), webcam smoke (Task 10).
- Test-mode (single camera) is exercised by the webcam smoke doc + the supervisor’s view-agnostic `process_frame` (detection runs on both halves regardless of source).
- Risk: `test_preview_streams_jpeg` may need the `client.stream(...)` form if `TestClient` blocks on the infinite MJPEG generator — noted inline (Task 7 Step 5).
