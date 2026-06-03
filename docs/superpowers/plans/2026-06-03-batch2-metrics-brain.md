# Metrics Brain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `metrics/` package — a pluggable, idempotent engine that turns a swing's stored pose timelines + phase moments + player height into golf `metric` rows (tilts, sways, spine, extension, hand depth, rough turns).

**Architecture:** Pure-function geometry layer (`geometry.py`) feeds small per-metric functions (`defs/*.py`), each registered in `registry.py` as a `MetricDef`. `compute.py` loads data via `store.repo`, builds an immutable `MetricContext` (smoothed pose, phase-frame lookup, pixels-per-inch ruler), runs every registered metric, then **replaces** the swing's metric rows (`clear_metrics` then `save_metrics`) so re-runs backfill new metrics without duplicating old ones. `run.py` is the CLI.

**Tech Stack:** Python 3.12, stdlib only (`math`, `statistics`, `dataclasses`, `argparse`), `pytest` (dev). Consumes the `store/` package (`store.repo`, `store.models`). No new third-party runtime deps. The vision rock's BlazePose landmark names are the contract for landmark lookup.

Spec: `docs/superpowers/specs/2026-06-03-batch2-metrics-brain-design.md`
Calibration source: `docs/superpowers/specs/2026-06-03-slice1-face-on-swing-metrics-design.md`

> **Python:** the `py` launcher is NOT on PATH. Use the full interpreter path in every command:
> `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`. Run all commands from the repo root `C:\Users\chris\Documents\Golf`.

> **Landmark names** (from `vision/pose.py` `LANDMARK_NAMES`, BlazePose 33). The metrics use exactly these strings:
> `nose`, `left_shoulder`, `right_shoulder`, `left_hip`, `right_hip`, `left_wrist`, `right_wrist`.
> Each `PoseFrame.landmarks` is a `list[Landmark]` with `.name`, `.x`, `.y` in **pixels of the view crop**, plus `.z`, `.visibility`. The helper `pick(landmarks, name)` looks one up by name.

> **Repo contract reminder:** every `store.repo` function takes an open `sqlite3.Connection` as its first argument. `get_pose_frames(conn, swing_id, view)`, `get_moments(conn, swing_id)`, `get_swing(conn, swing_id)`, `save_metrics(conn, swing_id, metrics)`, `clear_metrics(conn, swing_id)` already exist. `get_player(conn, id)` does **not** — Task 1 adds it.

> **Moment vocabulary** (as stored by the vision rock): `Moment.kind` ∈ {`address`, `takeaway`, `top`, `transition`, `impact`, ...}; `Moment.view` ∈ {`face_on`, `down_line`}. The metric engine only requires `address`, `top`, `impact`; missing ones are skipped and flagged. The pseudo-context `max` is **computed** (peak displacement across the swing), not a stored moment.

---

## File Structure

The `metrics/` package (sibling of `vision/` and `store/`):

- `metrics/__init__.py` — package marker.
- `metrics/geometry.py` — pure math: `pick`, `midpoint`, `line_angle_vs_horizontal`, `line_angle_vs_vertical`, `lateral_displacement`, `forward_vertical_displacement`, `foreshortening_to_rotation_deg`, `ppi_from_height`. No store imports.
- `metrics/context.py` — `MetricContext` dataclass + `frame_pose(view, frame_index)` / `pose_at_kind(view, kind)` / `address_pose(view)` accessors and pose smoothing helper.
- `metrics/registry.py` — `MetricDef(name, view, contexts, fn)` dataclass + `REGISTRY` list + `register()` + `all_defs()`. Imports every `defs/*` module so registration side-effects run.
- `metrics/defs/__init__.py` — package marker.
- `metrics/defs/tilt.py` — shoulder tilt, hip tilt (deg, exact; face_on).
- `metrics/defs/sway.py` — head sway, hip sway (inches via ppi; face_on).
- `metrics/defs/spine.py` — spine angle from vertical (deg, exact; down_line).
- `metrics/defs/extension.py` — early extension (inches; down_line).
- `metrics/defs/hand_depth.py` — hand depth from trail shoulder (inches; down_line).
- `metrics/defs/rotation.py` — rough shoulder turn + hip turn (deg, confidence=low; face_on).
- `metrics/compute.py` — `compute_metrics(conn, swing_id)` orchestrator (load → build context → run registry → clear+save).
- `metrics/run.py` — CLI: `--swing <id>` and `--all-missing`.
- `metrics/tests/__init__.py`
- `metrics/tests/conftest.py` — the in-memory `db` fixture (mirrors `store/tests/conftest.py`) + synthetic-swing builders.
- `metrics/tests/test_geometry.py`
- `metrics/tests/test_tilt.py`, `test_sway.py`, `test_spine.py`, `test_extension.py`, `test_hand_depth.py`, `test_rotation.py`
- `metrics/tests/test_compute.py`
- `metrics/tests/test_run.py`

Conventions:
- Metric `name`s are stable snake_case with unit suffix: `shoulder_tilt_deg`, `hip_tilt_deg`, `head_sway_in`, `hip_sway_in`, `spine_angle_deg`, `early_extension_in`, `hand_depth_in`, `shoulder_turn_deg`, `hip_turn_deg`.
- `method` strings: `exact` for calibration-free angles; `shoulder_ratio_0.24` for inch metrics; `foreshortening_2d;confidence=low` for the rough turns.
- `context` strings: `address`, `top`, `impact`, `max` (per the spec's per-metric context table).
- Angles in degrees, linear metrics in inches. Each metric fn returns `list[Metric]` (one per applicable context), with `swing_id` populated.

---

## Task 1: `get_player` repo getter

The orchestrator needs the player's height. `store.repo` has no `get_player`; add a tiny one.

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_players.py` (append)

- [ ] **Step 1: Write the failing test** (append to `store/tests/test_players.py`)

```python
def test_get_player_by_id(db):
    p = repo.get_or_create_player(db, "Heighted", 73.0, "R")
    got = repo.get_player(db, p.id)
    assert got.id == p.id and got.height_in == 73.0 and got.handedness == "R"
    assert repo.get_player(db, 99999) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/tests/test_players.py::test_get_player_by_id -v`
Expected: FAIL (`AttributeError: module 'store.repo' has no attribute 'get_player'`).

- [ ] **Step 3: Implement** (append to `store/repo.py`, after `list_players`)

```python
def get_player(conn, player_id):
    row = conn.execute("SELECT * FROM player WHERE id=?", (player_id,)).fetchone()
    if row is None:
        return None
    return Player(id=row["id"], name=row["name"], height_in=row["height_in"],
                  handedness=row["handedness"], created_at=row["created_at"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/tests/test_players.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_players.py
git commit -m "feat(store): add get_player(conn, id) getter"
```

---

## Task 2: Package scaffold + test fixture

**Files:**
- Create: `metrics/__init__.py`
- Create: `metrics/defs/__init__.py`
- Create: `metrics/tests/__init__.py`
- Create: `metrics/tests/conftest.py`

- [ ] **Step 1: Create the package markers**

`metrics/__init__.py`:
```python
"""GarageTEC metrics brain: pose timelines + moments + height -> golf numbers."""
```

`metrics/defs/__init__.py`: (empty file)

`metrics/tests/__init__.py`: (empty file)

- [ ] **Step 2: Create the test fixture + synthetic builders**

`metrics/tests/conftest.py`:
```python
"""Fixtures for the metrics brain tests.

`db` is a fresh in-memory store (mirrors store/tests/conftest.py).
`seed_swing` builds a synthetic swing: a player, a session, a swing, pose
frames for both views, and address/top/impact moments. Pose frames are built
from hand-authored landmark dicts so each metric has known geometry.
"""
import pytest

from store import db as dbmod
from store import repo
from store.models import Landmark, PoseFrame, Moment


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


def make_frame(swing_id, view, frame_index, coords, *, time_s=None):
    """coords: {name: (x, y)} -> a PoseFrame with z=0, visibility=1.0."""
    lms = [Landmark(name=n, x=float(x), y=float(y), z=0.0, visibility=1.0)
           for n, (x, y) in coords.items()]
    return PoseFrame(swing_id=swing_id, view=view, frame_index=frame_index,
                     time_s=time_s if time_s is not None else frame_index / 30.0,
                     landmarks=lms)


def seed_swing(db, *, height_in=72.0,
               face_on_frames=None, down_line_frames=None,
               moments=None):
    """Insert a complete synthetic swing. Returns the swing id.

    *_frames: list[(frame_index, {name: (x, y)})].
    moments: list[(kind, view, frame_index)].
    """
    pid = repo.get_or_create_player(db, "Synth", height_in, "R").id
    sid = repo.create_session(db, pid).id
    sw = repo.add_swing(db, sid, pid, "synthetic.MOV",
                        view_layout="side_by_side_LR", fps=30.0,
                        width=1920, height=1080).id
    if face_on_frames:
        repo.save_pose_frames(db, sw, "face_on", [
            make_frame(sw, "face_on", idx, coords) for idx, coords in face_on_frames])
    if down_line_frames:
        repo.save_pose_frames(db, sw, "down_line", [
            make_frame(sw, "down_line", idx, coords) for idx, coords in down_line_frames])
    if moments:
        repo.save_moments(db, sw, [
            Moment(sw, kind, view, idx, idx / 30.0)
            for (kind, view, idx) in moments])
    return sw
```

- [ ] **Step 3: Verify the fixture imports cleanly**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/ -q`
Expected: `no tests ran` (0 collected) with **no import/collection errors**.

- [ ] **Step 4: Commit**

```bash
git add metrics/__init__.py metrics/defs/__init__.py metrics/tests/__init__.py metrics/tests/conftest.py
git commit -m "chore(metrics): scaffold package + synthetic-swing test fixture"
```

---

## Task 3: geometry.py — pure math

**Files:**
- Create: `metrics/geometry.py`
- Test: `metrics/tests/test_geometry.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_geometry.py`:
```python
import math

import pytest

from store.models import Landmark
from metrics import geometry as g


def _lm(name, x, y):
    return Landmark(name=name, x=x, y=y, z=0.0, visibility=1.0)


def test_pick_finds_by_name():
    lms = [_lm("nose", 1.0, 2.0), _lm("left_hip", 3.0, 4.0)]
    assert g.pick(lms, "left_hip").x == 3.0
    assert g.pick(lms, "missing") is None


def test_midpoint():
    a, b = _lm("a", 0.0, 0.0), _lm("b", 10.0, 4.0)
    assert g.midpoint(a, b) == (5.0, 2.0)


def test_line_angle_vs_horizontal_level_is_zero():
    # two points at the same image-y -> 0 degrees
    a, b = _lm("ls", 100.0, 50.0), _lm("rs", 200.0, 50.0)
    assert abs(g.line_angle_vs_horizontal(a, b)) < 1e-9


def test_line_angle_vs_horizontal_45_up():
    # image y grows downward; right point 100px higher (smaller y) -> +45 deg
    a, b = _lm("ls", 100.0, 150.0), _lm("rs", 200.0, 50.0)
    assert g.line_angle_vs_horizontal(a, b) == pytest.approx(45.0, abs=1e-6)


def test_line_angle_vs_vertical_plumb_is_zero():
    # a vertical torso (same x) -> 0 deg from vertical
    top, bot = _lm("sh", 100.0, 50.0), _lm("hip", 100.0, 250.0)
    assert abs(g.line_angle_vs_vertical(top, bot)) < 1e-9


def test_line_angle_vs_vertical_30_lean():
    # leaned forward: dx = 200*tan(30) over dy=200
    dx = 200.0 * math.tan(math.radians(30.0))
    top, bot = _lm("sh", 100.0 + dx, 50.0), _lm("hip", 100.0, 250.0)
    assert g.line_angle_vs_vertical(top, bot) == pytest.approx(30.0, abs=1e-6)


def test_lateral_displacement_signed():
    # +x movement of 60 px
    assert g.lateral_displacement((100.0, 50.0), (160.0, 90.0)) == 60.0


def test_forward_vertical_displacement():
    fwd, vert = g.forward_vertical_displacement((100.0, 200.0), (130.0, 160.0))
    assert fwd == 30.0       # dx
    assert vert == -40.0     # dy (image y decreased -> stood up)


def test_ppi_from_height():
    # shoulder_px=100, height=72 -> real_shoulder_in=17.28 -> ppi ~5.787
    ppi = g.ppi_from_height(100.0, 72.0)
    assert ppi == pytest.approx(100.0 / (0.24 * 72.0), abs=1e-9)


def test_foreshortening_full_width_is_zero_turn():
    assert g.foreshortening_to_rotation_deg(100.0, 100.0) == pytest.approx(0.0, abs=1e-9)


def test_foreshortening_half_width_is_arccos_half():
    # width halved -> arccos(0.5) = 60 degrees
    assert g.foreshortening_to_rotation_deg(50.0, 100.0) == pytest.approx(60.0, abs=1e-6)


def test_foreshortening_clamps_over_full_width():
    # current wider than address (noise) -> clamp ratio to 1.0 -> 0 deg
    assert g.foreshortening_to_rotation_deg(130.0, 100.0) == pytest.approx(0.0, abs=1e-9)


def test_foreshortening_zero_address_width_returns_zero():
    assert g.foreshortening_to_rotation_deg(50.0, 0.0) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_geometry.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.geometry'`).

- [ ] **Step 3: Implement**

`metrics/geometry.py`:
```python
"""Pure geometry for swing metrics. No store imports; operates on Landmark
objects (with pixel .x/.y) and (x, y) tuples. Image coordinates: y grows
DOWNWARD, x grows toward image-right.
"""
import math
from typing import List, Optional, Tuple

from store.models import Landmark

Point = Tuple[float, float]

# Anthropometric ratio: biacromial (shoulder) breadth ~= 0.24 * standing height.
SHOULDER_HEIGHT_RATIO = 0.24


def pick(landmarks: List[Landmark], name: str) -> Optional[Landmark]:
    """Return the landmark with this name, or None if absent."""
    for lm in landmarks:
        if lm.name == name:
            return lm
    return None


def midpoint(a: Landmark, b: Landmark) -> Point:
    return ((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)


def line_angle_vs_horizontal(a: Landmark, b: Landmark) -> float:
    """Signed angle (deg) of the line a->b relative to the horizontal axis.
    Because image-y points down, we negate dy so that 'b higher than a'
    (smaller y) yields a positive angle. Range (-90, 90].
    """
    dx = b.x - a.x
    dy = b.y - a.y
    return math.degrees(math.atan2(-dy, dx))


def line_angle_vs_vertical(top: Landmark, bottom: Landmark) -> float:
    """Unsigned-magnitude lean (deg) of the segment top..bottom from a plumb
    vertical line. 0 = perfectly vertical. Uses horizontal run over vertical
    drop: atan2(|dx|, |dy|).
    """
    dx = top.x - bottom.x
    dy = top.y - bottom.y
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def lateral_displacement(ref: Point, cur: Point) -> float:
    """Signed horizontal pixel displacement (cur.x - ref.x)."""
    return cur[0] - ref[0]


def forward_vertical_displacement(ref: Point, cur: Point) -> Tuple[float, float]:
    """Return (forward_px, vertical_px) = (cur.x - ref.x, cur.y - ref.y).
    Vertical is signed image-y delta (negative = moved up / stood taller).
    """
    return (cur[0] - ref[0], cur[1] - ref[1])


def ppi_from_height(shoulder_px: float, height_in: float) -> float:
    """Pixels-per-inch from the Slice-1 ruler:
    ppi = shoulder_px / (0.24 * height_in). Returns 0.0 if undefined.
    """
    real_shoulder_in = SHOULDER_HEIGHT_RATIO * height_in
    if real_shoulder_in <= 0.0:
        return 0.0
    return shoulder_px / real_shoulder_in


def foreshortening_to_rotation_deg(current_width_px: float,
                                   address_width_px: float) -> float:
    """Rough 2D rotation estimate from segment-width foreshortening.
    A line of true length W projects to W*cos(theta) when rotated theta about a
    vertical axis, so theta = arccos(current / address). Full width -> 0 deg,
    half width -> 60 deg. Ratio clamped to [0, 1]; returns 0 if address width
    is non-positive. COARSE: callers must tag confidence=low.
    """
    if address_width_px <= 0.0:
        return 0.0
    ratio = current_width_px / address_width_px
    ratio = max(0.0, min(1.0, ratio))
    return math.degrees(math.acos(ratio))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_geometry.py -v`
Expected: PASS (all 13).

- [ ] **Step 5: Commit**

```bash
git add metrics/geometry.py metrics/tests/test_geometry.py
git commit -m "feat(metrics): pure geometry (angles, displacement, ppi, foreshortening)"
```

---

## Task 4: context.py — MetricContext + registry types

`MetricContext` carries smoothed pose for both views, a kind→frame index map, the
ppi ruler, and the player. `registry.py` defines `MetricDef` and the registry.

**Files:**
- Create: `metrics/context.py`
- Create: `metrics/registry.py`
- Test: `metrics/tests/test_context.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_context.py`:
```python
import pytest

from store.models import Player
from metrics.context import MetricContext, build_context
from metrics.registry import MetricDef, register, all_defs, REGISTRY
from metrics.tests.conftest import seed_swing
from store import repo


def test_build_context_computes_ppi_from_address_shoulders(db):
    # address shoulders 100px apart; height 72 -> ppi = 100 / (0.24*72)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                 "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
                 "nose": (500.0, 120.0)}),
            (10, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                  "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
                  "nose": (500.0, 120.0)}),
        ],
        moments=[("address", "face_on", 0), ("top", "face_on", 10)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == pytest.approx(100.0 / (0.24 * 72.0), abs=1e-6)
    assert ctx.player.height_in == 72.0
    assert ctx.frame_index_for("face_on", "address") == 0
    assert ctx.frame_index_for("face_on", "top") == 10
    # pose accessor returns the landmark list at that frame
    pose = ctx.pose_at("face_on", "address")
    from metrics.geometry import pick
    assert pick(pose, "nose").x == 500.0


def test_frame_index_for_missing_kind_returns_none(db):
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 200.0),
                             "right_shoulder": (550.0, 200.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    assert ctx.frame_index_for("face_on", "impact") is None
    assert ctx.pose_at("face_on", "impact") is None


def test_registry_register_and_all_defs():
    before = len(REGISTRY)
    d = MetricDef(name="dummy_test_metric", view="face_on",
                  contexts=("address",), fn=lambda ctx: [])
    register(d)
    assert d in all_defs()
    assert len(REGISTRY) == before + 1
    REGISTRY.remove(d)  # keep global registry clean for other tests
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_context.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.context'`).

- [ ] **Step 3: Implement**

`metrics/registry.py`:
```python
"""Metric registry. Each MetricDef.fn takes a MetricContext and returns a
list[Metric]. defs/* modules call register() at import time; importing this
module imports them so registration happens once.
"""
from dataclasses import dataclass
from typing import Callable, List, Sequence

from store.models import Metric

# Forward type only; avoid a circular import with context.py at module load.
MetricFn = Callable[[object], List[Metric]]


@dataclass(frozen=True)
class MetricDef:
    name: str
    view: str                 # "face_on" or "down_line"
    contexts: Sequence[str]   # e.g. ("address", "top", "impact")
    fn: MetricFn


REGISTRY: List[MetricDef] = []


def register(metric_def: MetricDef) -> MetricDef:
    REGISTRY.append(metric_def)
    return metric_def


def all_defs() -> List[MetricDef]:
    # Import defs so their register() side-effects populate REGISTRY exactly once.
    from metrics import defs  # noqa: F401  (triggers defs.__init__ imports)
    return list(REGISTRY)
```

`metrics/context.py`:
```python
"""MetricContext: everything a metric fn needs for one swing.

Holds smoothed pose timelines (per view), a (view, kind) -> frame_index map,
the pixels-per-inch ruler from the player's height + address shoulder width,
and the player. Built from the store by build_context().
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from store import repo
from store.models import Landmark, Player, PoseFrame
from metrics import geometry as g

# Number of frames in the centered moving-average smoothing window (odd).
SMOOTH_WINDOW = 3


@dataclass
class MetricContext:
    swing_id: int
    player: Player
    ppi: float
    fps: Optional[float]
    # view -> {frame_index -> landmarks}
    _pose: Dict[str, Dict[int, List[Landmark]]]
    # (view, kind) -> frame_index
    _moment_frame: Dict[Tuple[str, str], int]

    def frame_index_for(self, view: str, kind: str) -> Optional[int]:
        return self._moment_frame.get((view, kind))

    def frames(self, view: str) -> Dict[int, List[Landmark]]:
        return self._pose.get(view, {})

    def pose_at_frame(self, view: str, frame_index: int) -> Optional[List[Landmark]]:
        return self._pose.get(view, {}).get(frame_index)

    def pose_at(self, view: str, kind: str) -> Optional[List[Landmark]]:
        idx = self.frame_index_for(view, kind)
        if idx is None:
            return None
        return self.pose_at_frame(view, idx)


def _smooth(frames: List[PoseFrame], window: int) -> Dict[int, List[Landmark]]:
    """Centered moving average of each landmark's x/y across nearby frames.
    Only landmarks present in ALL frames of the window are averaged; otherwise
    the raw landmark at the center frame is kept. Returns {frame_index: lms}.
    """
    half = window // 2
    by_index = {f.frame_index: f for f in frames}
    order = sorted(by_index)
    pos = {idx: i for i, idx in enumerate(order)}
    out: Dict[int, List[Landmark]] = {}
    for idx in order:
        i = pos[idx]
        neighbours = [by_index[order[j]]
                      for j in range(max(0, i - half), min(len(order), i + half + 1))]
        center = by_index[idx]
        smoothed: List[Landmark] = []
        for lm in center.landmarks:
            xs, ys = [], []
            for nf in neighbours:
                n_lm = g.pick(nf.landmarks, lm.name)
                if n_lm is not None:
                    xs.append(n_lm.x)
                    ys.append(n_lm.y)
            ax = sum(xs) / len(xs) if xs else lm.x
            ay = sum(ys) / len(ys) if ys else lm.y
            smoothed.append(Landmark(name=lm.name, x=ax, y=ay, z=lm.z,
                                     visibility=lm.visibility))
        out[idx] = smoothed
    return out


def build_context(conn, swing_id: int) -> MetricContext:
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise ValueError(f"swing {swing_id} not found")
    player = repo.get_player(conn, swing.player_id)
    if player is None:
        raise ValueError(f"player {swing.player_id} for swing {swing_id} not found")

    pose: Dict[str, Dict[int, List[Landmark]]] = {}
    for view in ("face_on", "down_line"):
        frames = repo.get_pose_frames(conn, swing_id, view)
        pose[view] = _smooth(frames, SMOOTH_WINDOW) if frames else {}

    moment_frame: Dict[Tuple[str, str], int] = {}
    for m in repo.get_moments(conn, swing_id):
        if m.view is not None and m.frame_index is not None:
            moment_frame[(m.view, m.kind)] = m.frame_index

    ppi = _ppi_from_address(pose.get("face_on", {}), moment_frame, player)

    return MetricContext(swing_id=swing_id, player=player, ppi=ppi,
                         fps=swing.fps, _pose=pose, _moment_frame=moment_frame)


def _ppi_from_address(face_on: Dict[int, List[Landmark]],
                      moment_frame: Dict[Tuple[str, str], int],
                      player: Player) -> float:
    idx = moment_frame.get(("face_on", "address"))
    if idx is None or idx not in face_on:
        return 0.0
    lms = face_on[idx]
    ls = g.pick(lms, "left_shoulder")
    rs = g.pick(lms, "right_shoulder")
    if ls is None or rs is None:
        return 0.0
    shoulder_px = abs(rs.x - ls.x)
    return g.ppi_from_height(shoulder_px, player.height_in)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_context.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add metrics/context.py metrics/registry.py metrics/tests/test_context.py
git commit -m "feat(metrics): MetricContext (smoothed pose, ppi, moment lookup) + registry"
```

---

## Task 5: defs/tilt.py — shoulder & hip tilt (deg, exact)

Shoulder-line and hip-line angle vs horizontal, face-on, at address/top/impact.

**Files:**
- Create: `metrics/defs/tilt.py`
- Modify: `metrics/defs/__init__.py` (import the module so it registers)
- Test: `metrics/tests/test_tilt.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_tilt.py`:
```python
import pytest

from metrics.context import build_context
from metrics.defs import tilt
from metrics.tests.conftest import seed_swing


def _ctx_for_tilt(db):
    # address: shoulders level (0 deg), hips level (0 deg)
    # impact: right shoulder 100px higher than left over 100px run -> +45 deg
    #         hips level still (0 deg)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                 "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}),
            (20, {"left_shoulder": (450.0, 250.0), "right_shoulder": (550.0, 150.0),
                  "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}),
        ],
        moments=[("address", "face_on", 0), ("impact", "face_on", 20)],
    )
    return build_context(db, sw)


def test_shoulder_tilt_values_and_method(db):
    ctx = _ctx_for_tilt(db)
    metrics = tilt.shoulder_tilt(ctx)
    by_ctx = {m.context: m for m in metrics}
    assert by_ctx["address"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].value == pytest.approx(45.0, abs=1e-6)
    assert by_ctx["address"].unit == "deg"
    assert by_ctx["address"].method == "exact"
    assert by_ctx["address"].name == "shoulder_tilt_deg"
    assert by_ctx["address"].swing_id == ctx.swing_id


def test_hip_tilt_values(db):
    ctx = _ctx_for_tilt(db)
    by_ctx = {m.context: m for m in tilt.hip_tilt(ctx)}
    assert by_ctx["address"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].name == "hip_tilt_deg"
    assert by_ctx["impact"].method == "exact"


def test_tilt_skips_missing_moments(db):
    # only address present -> only one row, no crash for top/impact
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 200.0),
                             "right_shoulder": (550.0, 200.0),
                             "left_hip": (470.0, 400.0),
                             "right_hip": (530.0, 400.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    ctxs = {m.context for m in tilt.shoulder_tilt(ctx)}
    assert ctxs == {"address"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_tilt.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.tilt'`).

- [ ] **Step 3: Implement**

`metrics/defs/tilt.py`:
```python
"""Shoulder tilt and hip tilt: line angle vs horizontal, face-on, in degrees.
Exact (no calibration). Reported at address, top, impact.
"""
from typing import List

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("address", "top", "impact")


def _line_tilt(ctx, name, left_name, right_name) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        left = g.pick(pose, left_name)
        right = g.pick(pose, right_name)
        if left is None or right is None:
            continue
        angle = g.line_angle_vs_horizontal(left, right)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=angle, unit="deg", method="exact"))
    return out


def shoulder_tilt(ctx) -> List[Metric]:
    return _line_tilt(ctx, "shoulder_tilt_deg", "left_shoulder", "right_shoulder")


def hip_tilt(ctx) -> List[Metric]:
    return _line_tilt(ctx, "hip_tilt_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_tilt_deg", view="face_on",
                   contexts=CONTEXTS, fn=shoulder_tilt))
register(MetricDef(name="hip_tilt_deg", view="face_on",
                   contexts=CONTEXTS, fn=hip_tilt))
```

`metrics/defs/__init__.py` (replace empty content with imports — each import runs its `register()` calls):
```python
"""Importing this package registers every metric def."""
from metrics.defs import tilt  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_tilt.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/tilt.py metrics/defs/__init__.py metrics/tests/test_tilt.py
git commit -m "feat(metrics): shoulder & hip tilt (deg, exact)"
```

---

## Task 6: defs/sway.py — head & hip sway (inches via ppi)

Lateral displacement of head-center (nose) and hip-center from the **address**
position, converted to inches with the ppi ruler. Reported at top, impact, and
**max** (peak absolute lateral displacement across the swing). Sign: positive =
toward target, inferred from net hip motion top→impact.

**Files:**
- Create: `metrics/defs/sway.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_sway.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_sway.py`:
```python
import pytest

from metrics.context import build_context
from metrics.defs import sway
from metrics.tests.conftest import seed_swing


def _ctx_for_sway(db):
    # height 72, address shoulders 100px -> ppi = 100/(0.24*72) = 5.78704 px/in
    # hip center moves +57.87px from address by impact -> +10.0 in (toward +x).
    # net hip motion top->impact is +x, so +x is "toward target": sign stays +.
    # frames: address(0), mid-burst(10) hip at +28.9px, top(20), impact(30) +57.87px
    ppi = 100.0 / (0.24 * 72.0)
    dx_impact = 10.0 * ppi  # 57.870...
    dx_mid = 12.0 * ppi     # 69.44 -> this is the MAX (bigger than impact)
    base = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
            "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
            "nose": (500.0, 120.0)}

    def shifted(dx):
        c = dict(base)
        c["left_hip"] = (470.0 + dx, 400.0)
        c["right_hip"] = (530.0 + dx, 400.0)
        c["nose"] = (500.0 + dx, 120.0)
        return c

    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, base),
            (10, shifted(dx_mid)),
            (20, shifted(dx_mid * 0.5)),
            (30, shifted(dx_impact)),
        ],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 30)],
    )
    return build_context(db, sw)


def test_hip_sway_inches_and_method(db):
    ctx = _ctx_for_sway(db)
    by_ctx = {m.context: m for m in sway.hip_sway(ctx)}
    assert by_ctx["impact"].value == pytest.approx(10.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "hip_sway_in"
    # max sway picks the frame with largest |dx| (the 12-in mid frame)
    assert by_ctx["max"].value == pytest.approx(12.0, abs=1e-3)


def test_head_sway_inches(db):
    ctx = _ctx_for_sway(db)
    by_ctx = {m.context: m for m in sway.head_sway(ctx)}
    assert by_ctx["impact"].value == pytest.approx(10.0, abs=1e-3)
    assert by_ctx["impact"].name == "head_sway_in"
    assert by_ctx["max"].value == pytest.approx(12.0, abs=1e-3)


def test_sway_zero_when_no_ppi(db):
    # no address moment -> ppi 0 -> sway fns return nothing (cannot convert)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(20, {"left_hip": (470.0, 400.0),
                              "right_hip": (530.0, 400.0),
                              "nose": (500.0, 120.0)})],
        moments=[("top", "face_on", 20)],
    )
    ctx = build_context(db, sw)
    assert sway.hip_sway(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_sway.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.sway'`).

- [ ] **Step 3: Implement**

`metrics/defs/sway.py`:
```python
"""Head sway and hip sway: lateral displacement of a body center from its
ADDRESS position, in inches via the shoulder-ratio ppi ruler. Reported at top,
impact, and max (peak |displacement| over the swing). Positive = toward target;
target side inferred from net hip motion address->impact.
"""
from typing import Callable, List, Optional

from store.models import Landmark, Metric
from metrics import geometry as g

from metrics.registry import MetricDef, register

REPORT_CONTEXTS = ("top", "impact")
METHOD = "shoulder_ratio_0.24"


def _center(pose: List[Landmark], kind: str) -> Optional[tuple]:
    if kind == "head":
        n = g.pick(pose, "nose")
        return (n.x, n.y) if n is not None else None
    lh = g.pick(pose, "left_hip")
    rh = g.pick(pose, "right_hip")
    if lh is None or rh is None:
        return None
    return g.midpoint(lh, rh)


def _sway(ctx, name: str, body: str) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    addr_pose = ctx.pose_at("face_on", "address")
    if addr_pose is None:
        return []
    ref = _center(addr_pose, body)
    if ref is None:
        return []

    # Direction sign: net x-motion of hip center address->impact; default +1.
    sign = _target_sign(ctx, ref if body == "hip" else None)

    out: List[Metric] = []
    for kind in REPORT_CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        cur = _center(pose, body)
        if cur is None:
            continue
        dx_px = g.lateral_displacement(ref, cur)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=sign * dx_px / ctx.ppi, unit="in", method=METHOD))

    # max: scan every frame, pick the largest |dx|.
    max_px = 0.0
    for _idx, pose in sorted(ctx.frames("face_on").items()):
        cur = _center(pose, body)
        if cur is None:
            continue
        dx_px = g.lateral_displacement(ref, cur)
        if abs(dx_px) > abs(max_px):
            max_px = dx_px
    if max_px != 0.0:
        out.append(Metric(swing_id=ctx.swing_id, name=name, context="max",
                          value=sign * max_px / ctx.ppi, unit="in", method=METHOD))
    return out


def _target_sign(ctx, hip_ref) -> float:
    """+1 if net hip-center x increases address->impact, else -1. Falls back to
    +1 when impact or hips are missing."""
    addr = ctx.pose_at("face_on", "address")
    imp = ctx.pose_at("face_on", "impact")
    if addr is None or imp is None:
        return 1.0
    a = _center(addr, "hip")
    b = _center(imp, "hip")
    if a is None or b is None:
        return 1.0
    return 1.0 if (b[0] - a[0]) >= 0 else -1.0


def hip_sway(ctx) -> List[Metric]:
    return _sway(ctx, "hip_sway_in", "hip")


def head_sway(ctx) -> List[Metric]:
    return _sway(ctx, "head_sway_in", "head")


register(MetricDef(name="hip_sway_in", view="face_on",
                   contexts=("top", "impact", "max"), fn=hip_sway))
register(MetricDef(name="head_sway_in", view="face_on",
                   contexts=("top", "impact", "max"), fn=head_sway))
```

Append to `metrics/defs/__init__.py`:
```python
from metrics.defs import sway  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_sway.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/sway.py metrics/defs/__init__.py metrics/tests/test_sway.py
git commit -m "feat(metrics): head & hip sway (inches via shoulder-ratio ppi)"
```

---

## Task 7: defs/spine.py — spine angle (deg, exact, down-line)

Torso lean (hip-center → shoulder-center) from vertical, down-line, at
address/top/impact.

**Files:**
- Create: `metrics/defs/spine.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_spine.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_spine.py`:
```python
import math

import pytest

from metrics.context import build_context
from metrics.defs import spine
from metrics.tests.conftest import seed_swing


def test_spine_angle_30deg(db):
    # down-line: shoulder center leaned forward 30 deg from the hip center over
    # a 200px vertical drop. dx = 200*tan(30).
    dx = 200.0 * math.tan(math.radians(30.0))
    coords = {
        "left_shoulder": (600.0 + dx, 300.0), "right_shoulder": (600.0 + dx, 300.0),
        "left_hip": (600.0, 500.0), "right_hip": (600.0, 500.0),
    }
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(0, coords), (20, coords)],
        moments=[("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    ctx = build_context(db, sw)
    by_ctx = {m.context: m for m in spine.spine_angle(ctx)}
    assert by_ctx["address"].value == pytest.approx(30.0, abs=1e-6)
    assert by_ctx["address"].unit == "deg"
    assert by_ctx["address"].method == "exact"
    assert by_ctx["address"].name == "spine_angle_deg"


def test_spine_uses_down_line_view_not_face_on(db):
    # face_on present but no down_line -> no rows (spine is a DTL metric)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0),
                             "left_hip": (470.0, 500.0),
                             "right_hip": (530.0, 500.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    assert spine.spine_angle(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_spine.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.spine'`).

- [ ] **Step 3: Implement**

`metrics/defs/spine.py`:
```python
"""Spine angle: torso (hip-center -> shoulder-center) lean from vertical,
down-line view, in degrees. Exact. Reported at address, top, impact.
"""
from typing import List

from store.models import Landmark, Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("address", "top", "impact")


def _center_landmark(pose, a_name, b_name, out_name):
    a = g.pick(pose, a_name)
    b = g.pick(pose, b_name)
    if a is None or b is None:
        return None
    cx, cy = g.midpoint(a, b)
    return Landmark(name=out_name, x=cx, y=cy, z=0.0, visibility=1.0)


def spine_angle(ctx) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("down_line", kind)
        if pose is None:
            continue
        shoulder = _center_landmark(pose, "left_shoulder", "right_shoulder", "sh_c")
        hip = _center_landmark(pose, "left_hip", "right_hip", "hip_c")
        if shoulder is None or hip is None:
            continue
        angle = g.line_angle_vs_vertical(shoulder, hip)
        out.append(Metric(swing_id=ctx.swing_id, name="spine_angle_deg",
                          context=kind, value=angle, unit="deg", method="exact"))
    return out


register(MetricDef(name="spine_angle_deg", view="down_line",
                   contexts=CONTEXTS, fn=spine_angle))
```

Append to `metrics/defs/__init__.py`:
```python
from metrics.defs import spine  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_spine.py -v`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/spine.py metrics/defs/__init__.py metrics/tests/test_spine.py
git commit -m "feat(metrics): spine angle from vertical (deg, exact, down-line)"
```

---

## Task 8: defs/extension.py — early extension (inches, down-line)

Forward + vertical hip-center shift from address (hips moving toward the ball /
standing up). Down-line. Reported at impact (vs address) and max. Magnitude in
inches via ppi; we report the combined forward+up displacement magnitude.

**Files:**
- Create: `metrics/defs/extension.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_extension.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_extension.py`:
```python
import pytest

from metrics.context import build_context
from metrics.defs import extension
from metrics.tests.conftest import seed_swing


def _ctx(db):
    # ppi = 100/(0.24*72) = 5.78704 px/in. Hip center moves +3in forward (+x)
    # and 4in up (-y) by impact -> magnitude 5in. A mid frame moves 6/8 -> 10in
    # magnitude (the max). Address shoulders 100px for ppi.
    ppi = 100.0 / (0.24 * 72.0)
    base = {"left_shoulder": (600.0, 300.0), "right_shoulder": (700.0, 300.0),
            "left_hip": (640.0, 500.0), "right_hip": (660.0, 500.0)}

    def shifted(fwd_in, up_in):
        c = dict(base)
        dx, dy = fwd_in * ppi, -up_in * ppi
        c["left_hip"] = (640.0 + dx, 500.0 + dy)
        c["right_hip"] = (660.0 + dx, 500.0 + dy)
        return c

    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[
            (0, base),
            (10, shifted(6.0, 8.0)),   # magnitude 10in (the MAX)
            (20, shifted(3.0, 4.0)),   # impact -> magnitude 5in
        ],
        moments=[("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    return build_context(db, sw)


def test_early_extension_impact_and_max(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in extension.early_extension(ctx)}
    assert by_ctx["impact"].value == pytest.approx(5.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "early_extension_in"
    assert by_ctx["max"].value == pytest.approx(10.0, abs=1e-3)


def test_early_extension_needs_ppi(db):
    # ppi needs face_on address shoulders; here address shoulders exist down_line
    # but ppi is computed from FACE_ON address -> absent -> 0 -> no rows.
    ctx = _ctx(db)
    # sanity: the fixture above has no face_on frames, so ppi is 0
    assert ctx.ppi == 0.0
    assert extension.early_extension(ctx) == []
```

> Note: `_ctx` deliberately seeds only `down_line` frames, so `ppi` (computed
> from the **face-on** address shoulders) is 0 and `early_extension` returns
> `[]` — that is exactly what `test_early_extension_needs_ppi` asserts. The
> first test, `test_early_extension_impact_and_max`, therefore needs a context
> WITH ppi. Replace `_ctx` so it also seeds a face-on address frame:

Update `_ctx` to additionally pass `face_on_frames` with an address frame whose
shoulders are 100px apart:

```python
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0)})],
        down_line_frames=[
            (0, base),
            (10, shifted(6.0, 8.0)),
            (20, shifted(3.0, 4.0)),
        ],
        moments=[("address", "face_on", 0),
                 ("address", "down_line", 0), ("impact", "down_line", 20)],
    )
```

and split the no-ppi assertion into its own swing (down_line only):

```python
def test_early_extension_needs_ppi(db):
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(0, {"left_hip": (640.0, 500.0),
                              "right_hip": (660.0, 500.0)}),
                          (20, {"left_hip": (700.0, 460.0),
                               "right_hip": (720.0, 460.0)})],
        moments=[("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == 0.0
    assert extension.early_extension(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_extension.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.extension'`).

- [ ] **Step 3: Implement**

`metrics/defs/extension.py`:
```python
"""Early extension: hip-center forward (+x toward ball) and vertical (up) shift
from address, down-line, magnitude in inches via ppi. Reported at impact (vs
address) and max (peak magnitude over the swing).
"""
import math
from typing import List, Optional

from store.models import Landmark, Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

METHOD = "shoulder_ratio_0.24"


def _hip_center(pose) -> Optional[tuple]:
    lh = g.pick(pose, "left_hip")
    rh = g.pick(pose, "right_hip")
    if lh is None or rh is None:
        return None
    return g.midpoint(lh, rh)


def _magnitude_in(ref, cur, ppi) -> float:
    fwd, vert = g.forward_vertical_displacement(ref, cur)
    return math.hypot(fwd, vert) / ppi


def early_extension(ctx) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    addr = ctx.pose_at("down_line", "address")
    if addr is None:
        return []
    ref = _hip_center(addr)
    if ref is None:
        return []

    out: List[Metric] = []
    imp = ctx.pose_at("down_line", "impact")
    if imp is not None:
        cur = _hip_center(imp)
        if cur is not None:
            out.append(Metric(swing_id=ctx.swing_id, name="early_extension_in",
                              context="impact", value=_magnitude_in(ref, cur, ctx.ppi),
                              unit="in", method=METHOD))

    max_mag = 0.0
    for _idx, pose in sorted(ctx.frames("down_line").items()):
        cur = _hip_center(pose)
        if cur is None:
            continue
        mag = _magnitude_in(ref, cur, ctx.ppi)
        if mag > max_mag:
            max_mag = mag
    if max_mag > 0.0:
        out.append(Metric(swing_id=ctx.swing_id, name="early_extension_in",
                          context="max", value=max_mag, unit="in", method=METHOD))
    return out


register(MetricDef(name="early_extension_in", view="down_line",
                   contexts=("impact", "max"), fn=early_extension))
```

Append to `metrics/defs/__init__.py`:
```python
from metrics.defs import extension  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_extension.py -v`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/extension.py metrics/defs/__init__.py metrics/tests/test_extension.py
git commit -m "feat(metrics): early extension (inches, down-line)"
```

---

## Task 9: defs/hand_depth.py — hand depth (inches, down-line)

Horizontal distance of the hands (mid-wrist) from the trail shoulder, down-line,
in inches via ppi. Reported at top and impact.

**Files:**
- Create: `metrics/defs/hand_depth.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_hand_depth.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_hand_depth.py`:
```python
import pytest

from metrics.context import build_context
from metrics.defs import hand_depth
from metrics.tests.conftest import seed_swing


def _ctx(db):
    # ppi from face_on address shoulders 100px, height 72 -> 5.78704 px/in.
    # Down-line: trail shoulder (right_shoulder for a RH golfer) at x=700.
    # mid-wrist x=700 + 4in*ppi at impact -> hand_depth 4in.
    ppi = 100.0 / (0.24 * 72.0)
    dl = {"left_shoulder": (700.0, 300.0), "right_shoulder": (700.0, 300.0),
          "left_wrist": (700.0 + 4.0 * ppi, 450.0),
          "right_wrist": (700.0 + 4.0 * ppi, 450.0),
          "left_hip": (700.0, 500.0), "right_hip": (700.0, 500.0)}
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0)})],
        down_line_frames=[(20, dl), (30, dl)],
        moments=[("address", "face_on", 0),
                 ("top", "down_line", 20), ("impact", "down_line", 30)],
    )
    return build_context(db, sw)


def test_hand_depth_inches(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in hand_depth.hand_depth(ctx)}
    assert by_ctx["impact"].value == pytest.approx(4.0, abs=1e-3)
    assert by_ctx["top"].value == pytest.approx(4.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "hand_depth_in"


def test_hand_depth_skips_without_ppi(db):
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(30, {"right_shoulder": (700.0, 300.0),
                               "left_shoulder": (700.0, 300.0),
                               "left_wrist": (760.0, 450.0),
                               "right_wrist": (760.0, 450.0)})],
        moments=[("impact", "down_line", 30)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == 0.0
    assert hand_depth.hand_depth(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_hand_depth.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.hand_depth'`).

- [ ] **Step 3: Implement**

`metrics/defs/hand_depth.py`:
```python
"""Hand depth: horizontal distance of the hands (mid-wrist) from the trail
shoulder, down-line, in inches via ppi. Reported at top and impact. The trail
shoulder is the right shoulder for a right-handed player, left for a lefty.
"""
from typing import List, Optional

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("top", "impact")
METHOD = "shoulder_ratio_0.24"


def _mid_wrist_x(pose) -> Optional[float]:
    lw = g.pick(pose, "left_wrist")
    rw = g.pick(pose, "right_wrist")
    if lw is None or rw is None:
        return None
    return (lw.x + rw.x) / 2.0


def _trail_shoulder_name(handedness) -> str:
    return "left_shoulder" if (handedness or "R").upper() == "L" else "right_shoulder"


def hand_depth(ctx) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    trail = _trail_shoulder_name(ctx.player.handedness)
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("down_line", kind)
        if pose is None:
            continue
        shoulder = g.pick(pose, trail)
        wrist_x = _mid_wrist_x(pose)
        if shoulder is None or wrist_x is None:
            continue
        depth_px = abs(wrist_x - shoulder.x)
        out.append(Metric(swing_id=ctx.swing_id, name="hand_depth_in",
                          context=kind, value=depth_px / ctx.ppi, unit="in",
                          method=METHOD))
    return out


register(MetricDef(name="hand_depth_in", view="down_line",
                   contexts=CONTEXTS, fn=hand_depth))
```

Append to `metrics/defs/__init__.py`:
```python
from metrics.defs import hand_depth  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_hand_depth.py -v`
Expected: PASS (2).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/hand_depth.py metrics/defs/__init__.py metrics/tests/test_hand_depth.py
git commit -m "feat(metrics): hand depth from trail shoulder (inches, down-line)"
```

---

## Task 10: defs/rotation.py — rough shoulder & hip turn (deg, confidence=low)

Estimated rotation from shoulder-width / hip-width foreshortening vs address,
face-on, at top and impact. These are coarse; every row carries
`method="foreshortening_2d;confidence=low"`.

**Files:**
- Create: `metrics/defs/rotation.py`
- Modify: `metrics/defs/__init__.py`
- Test: `metrics/tests/test_rotation.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_rotation.py`:
```python
import pytest

from metrics.context import build_context
from metrics.defs import rotation
from metrics.tests.conftest import seed_swing

LOW = "foreshortening_2d;confidence=low"


def _ctx(db):
    # address shoulders 100px, hips 60px wide.
    # top: shoulders project to 50px -> arccos(0.5)=60deg; hips to 30px -> 60deg.
    # impact: shoulders back to ~86.6px -> arccos(0.866)=30deg.
    addr = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
            "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}
    top = {"left_shoulder": (475.0, 200.0), "right_shoulder": (525.0, 200.0),
           "left_hip": (485.0, 400.0), "right_hip": (515.0, 400.0)}
    impact = {"left_shoulder": (456.7, 200.0), "right_shoulder": (543.3, 200.0),
              "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, addr), (20, top), (40, impact)],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 40)],
    )
    return build_context(db, sw)


def test_shoulder_turn_estimate_and_low_confidence(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in rotation.shoulder_turn(ctx)}
    assert by_ctx["top"].value == pytest.approx(60.0, abs=0.1)
    assert by_ctx["impact"].value == pytest.approx(30.0, abs=0.2)
    assert by_ctx["top"].unit == "deg"
    assert by_ctx["top"].method == LOW
    assert by_ctx["top"].name == "shoulder_turn_deg"


def test_hip_turn_estimate_and_low_confidence(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in rotation.hip_turn(ctx)}
    assert by_ctx["top"].value == pytest.approx(60.0, abs=0.1)
    assert by_ctx["top"].method == LOW
    assert by_ctx["top"].name == "hip_turn_deg"


def test_rotation_skips_without_address(db):
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(20, {"left_shoulder": (475.0, 200.0),
                             "right_shoulder": (525.0, 200.0)})],
        moments=[("top", "face_on", 20)],
    )
    ctx = build_context(db, sw)
    assert rotation.shoulder_turn(ctx) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_rotation.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.defs.rotation'`).

- [ ] **Step 3: Implement**

`metrics/defs/rotation.py`:
```python
"""Rough 2D shoulder turn and hip turn from width foreshortening vs address,
face-on, at top and impact. COARSE estimates: every row is tagged
method="foreshortening_2d;confidence=low".
"""
from typing import List, Optional

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("top", "impact")
METHOD = "foreshortening_2d;confidence=low"


def _width(pose, left_name, right_name) -> Optional[float]:
    left = g.pick(pose, left_name)
    right = g.pick(pose, right_name)
    if left is None or right is None:
        return None
    return abs(right.x - left.x)


def _turn(ctx, name, left_name, right_name) -> List[Metric]:
    addr = ctx.pose_at("face_on", "address")
    if addr is None:
        return []
    addr_w = _width(addr, left_name, right_name)
    if addr_w is None or addr_w <= 0.0:
        return []
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        cur_w = _width(pose, left_name, right_name)
        if cur_w is None:
            continue
        deg = g.foreshortening_to_rotation_deg(cur_w, addr_w)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_turn(ctx) -> List[Metric]:
    return _turn(ctx, "shoulder_turn_deg", "left_shoulder", "right_shoulder")


def hip_turn(ctx) -> List[Metric]:
    return _turn(ctx, "hip_turn_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_turn_deg", view="face_on",
                   contexts=CONTEXTS, fn=shoulder_turn))
register(MetricDef(name="hip_turn_deg", view="face_on",
                   contexts=CONTEXTS, fn=hip_turn))
```

Append to `metrics/defs/__init__.py`:
```python
from metrics.defs import rotation  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_rotation.py -v`
Expected: PASS (3).

- [ ] **Step 5: Commit**

```bash
git add metrics/defs/rotation.py metrics/defs/__init__.py metrics/tests/test_rotation.py
git commit -m "feat(metrics): rough shoulder & hip turn (foreshortening, confidence=low)"
```

---

## Task 11: compute.py — orchestrator (load → run → replace)

Load context, run every registered metric, then `clear_metrics` + `save_metrics`
so recompute is idempotent.

**Files:**
- Create: `metrics/compute.py`
- Test: `metrics/tests/test_compute.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_compute.py`:
```python
import pytest

from store import repo
from metrics.compute import compute_metrics
from metrics.tests.conftest import seed_swing


def _full_swing(db):
    # A swing with both views and address/top/impact so most metrics produce rows.
    addr_fo = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
               "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
               "nose": (500.0, 120.0)}
    top_fo = {"left_shoulder": (470.0, 210.0), "right_shoulder": (540.0, 190.0),
              "left_hip": (480.0, 400.0), "right_hip": (520.0, 400.0),
              "nose": (505.0, 122.0)}
    imp_fo = {"left_shoulder": (450.0, 240.0), "right_shoulder": (550.0, 160.0),
              "left_hip": (490.0, 400.0), "right_hip": (550.0, 400.0),
              "nose": (520.0, 120.0)}
    addr_dl = {"left_shoulder": (700.0, 300.0), "right_shoulder": (700.0, 300.0),
               "left_hip": (700.0, 500.0), "right_hip": (700.0, 500.0),
               "left_wrist": (740.0, 450.0), "right_wrist": (740.0, 450.0)}
    imp_dl = {"left_shoulder": (720.0, 290.0), "right_shoulder": (720.0, 290.0),
              "left_hip": (730.0, 470.0), "right_hip": (730.0, 470.0),
              "left_wrist": (760.0, 450.0), "right_wrist": (760.0, 450.0)}
    return seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, addr_fo), (20, top_fo), (40, imp_fo)],
        down_line_frames=[(0, addr_dl), (20, addr_dl), (40, imp_dl)],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 40),
                 ("address", "down_line", 0), ("top", "down_line", 20),
                 ("impact", "down_line", 40)],
    )


def test_compute_writes_all_metric_families(db):
    sw = _full_swing(db)
    written = compute_metrics(db, sw)
    names = {m.name for m in written}
    assert {"shoulder_tilt_deg", "hip_tilt_deg", "head_sway_in", "hip_sway_in",
            "spine_angle_deg", "early_extension_in", "hand_depth_in",
            "shoulder_turn_deg", "hip_turn_deg"} <= names
    # persisted to the store
    stored = repo.get_metrics(db, sw)
    assert len(stored) == len(written)


def test_compute_is_idempotent_no_duplicates(db):
    sw = _full_swing(db)
    first = compute_metrics(db, sw)
    n1 = len(repo.get_metrics(db, sw))
    second = compute_metrics(db, sw)
    n2 = len(repo.get_metrics(db, sw))
    assert n1 == n2  # replaced, not appended
    assert len(first) == len(second)


def test_compute_low_confidence_tag_on_rotations(db):
    sw = _full_swing(db)
    compute_metrics(db, sw)
    rot = [m for m in repo.get_metrics(db, sw)
           if m.name in ("shoulder_turn_deg", "hip_turn_deg")]
    assert rot  # present
    assert all(m.method == "foreshortening_2d;confidence=low" for m in rot)


def test_compute_reliable_methods(db):
    sw = _full_swing(db)
    compute_metrics(db, sw)
    by_name = {}
    for m in repo.get_metrics(db, sw):
        by_name.setdefault(m.name, m)
    assert by_name["shoulder_tilt_deg"].method == "exact"
    assert by_name["spine_angle_deg"].method == "exact"
    assert by_name["hip_sway_in"].method == "shoulder_ratio_0.24"
    assert by_name["hand_depth_in"].method == "shoulder_ratio_0.24"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_compute.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'metrics.compute'`).

- [ ] **Step 3: Implement**

`metrics/compute.py`:
```python
"""Orchestrator: build a MetricContext for a swing, run every registered metric
def, and REPLACE the swing's metric rows (clear then save) for idempotent
recompute.
"""
from typing import List

from store import repo
from store.models import Metric
from metrics.context import build_context
from metrics.registry import all_defs


def compute_metrics(conn, swing_id: int) -> List[Metric]:
    """Compute and persist all metrics for one swing. Returns the saved list."""
    ctx = build_context(conn, swing_id)
    results: List[Metric] = []
    for metric_def in all_defs():
        try:
            results.extend(metric_def.fn(ctx))
        except Exception:
            # A single metric must never sink the whole recompute; skip + move on.
            # (Pose gaps / missing moments are already guarded inside each fn.)
            continue
    repo.clear_metrics(conn, swing_id)
    repo.save_metrics(conn, swing_id, results)
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_compute.py -v`
Expected: PASS (5).

- [ ] **Step 5: Commit**

```bash
git add metrics/compute.py metrics/tests/test_compute.py
git commit -m "feat(metrics): compute orchestrator (idempotent clear+save)"
```

---

## Task 12: run.py — CLI (`--swing`, `--all-missing`)

**Files:**
- Create: `metrics/run.py`
- Test: `metrics/tests/test_run.py`

- [ ] **Step 1: Write the failing test**

`metrics/tests/test_run.py`:
```python
import pytest

from store import repo
from metrics import run as runmod
from metrics.tests.test_compute import _full_swing


def test_swings_missing_metrics_lists_only_uncomputed(db):
    sw1 = _full_swing(db)
    sw2 = _full_swing(db)
    # compute sw1 only
    from metrics.compute import compute_metrics
    compute_metrics(db, sw1)
    missing = runmod.swings_missing_metrics(db)
    assert sw2 in missing and sw1 not in missing


def test_run_swing_computes_one(db):
    sw = _full_swing(db)
    code = runmod.run(db, ["--swing", str(sw)])
    assert code == 0
    assert repo.get_metrics(db, sw)  # non-empty


def test_run_all_missing_computes_all_uncomputed(db):
    sw1 = _full_swing(db)
    sw2 = _full_swing(db)
    code = runmod.run(db, ["--all-missing"])
    assert code == 0
    assert repo.get_metrics(db, sw1)
    assert repo.get_metrics(db, sw2)


def test_run_requires_a_mode(db):
    with pytest.raises(SystemExit):
        runmod.run(db, [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_run.py -v`
Expected: FAIL (`AttributeError: module 'metrics.run' has no attribute 'run'`).

- [ ] **Step 3: Implement**

`metrics/run.py`:
```python
"""CLI for the metrics brain.

    python -m metrics.run --swing 42
    python -m metrics.run --all-missing

Both accept an explicit DB via --db PATH (defaults to the store's default path).
The run(conn, argv) function takes an open connection so tests use :memory:.
"""
import argparse
import sys
from typing import List

from store import db as dbmod
from store import repo
from metrics.compute import compute_metrics


def swings_missing_metrics(conn) -> List[int]:
    """Swing ids that have zero metric rows, in id order."""
    rows = conn.execute(
        "SELECT sw.id FROM swing sw "
        "LEFT JOIN metric m ON m.swing_id = sw.id "
        "WHERE m.id IS NULL GROUP BY sw.id ORDER BY sw.id").fetchall()
    return [r["id"] for r in rows]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metrics.run",
                                description="Compute swing metrics.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--swing", type=int, help="compute metrics for one swing id")
    g.add_argument("--all-missing", action="store_true",
                   help="compute metrics for every swing lacking metrics")
    p.add_argument("--db", default=None, help="path to the SQLite db (optional)")
    return p


def run(conn, argv: List[str]) -> int:
    """Run with an already-open connection (used by tests and main)."""
    args = _build_parser().parse_args(argv)
    if args.swing is not None:
        written = compute_metrics(conn, args.swing)
        print(f"swing {args.swing}: wrote {len(written)} metrics")
        return 0
    ids = swings_missing_metrics(conn)
    total = 0
    for swing_id in ids:
        written = compute_metrics(conn, swing_id)
        total += len(written)
        print(f"swing {swing_id}: wrote {len(written)} metrics")
    print(f"done: {len(ids)} swings, {total} metrics")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Peek for --db without consuming the required mode group.
    db_path = None
    if "--db" in argv:
        i = argv.index("--db")
        db_path = argv[i + 1]
    conn = dbmod.connect(db_path)
    try:
        return run(conn, argv)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/tests/test_run.py -v`
Expected: PASS (4).

- [ ] **Step 5: Commit**

```bash
git add metrics/run.py metrics/tests/test_run.py
git commit -m "feat(metrics): run CLI (--swing / --all-missing)"
```

---

## Task 13: Full suite + done criteria

- [ ] **Step 1: Run the whole metrics + store suite**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest metrics/ store/ -v`
Expected: PASS (all green).

- [ ] **Step 2: Smoke the CLI help (no traceback)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m metrics.run --help`
Expected: argparse usage text listing `--swing`, `--all-missing`, `--db`. Exit 0.

- [ ] **Step 3: Final commit (if anything is uncommitted)**

```bash
git add -A
git commit -m "test(metrics): full suite green for metrics brain"
```

---

## Done criteria

- `python -m pytest metrics/ store/ -v` is fully green.
- `metrics/` exposes the full v1 metric set: `shoulder_tilt_deg`, `hip_tilt_deg`
  (exact); `head_sway_in`, `hip_sway_in` (shoulder_ratio_0.24); `spine_angle_deg`
  (exact); `early_extension_in`, `hand_depth_in` (shoulder_ratio_0.24);
  `shoulder_turn_deg`, `hip_turn_deg` (foreshortening_2d;confidence=low).
- Recompute is idempotent (clear_metrics then save_metrics): re-running a swing
  produces no duplicate rows.
- Each metric records its `method` (incl. calibration + confidence) so method
  changes are auditable; rough turns carry `confidence=low`.
- New metrics are a single `defs/*.py` + `register()` + one import line in
  `defs/__init__.py`; re-running `--all-missing` (or per-swing) backfills them.
- No new third-party runtime dependency; only `store/` is consumed.
```
