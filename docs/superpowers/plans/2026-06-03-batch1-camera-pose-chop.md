# Camera + Pose + Swing-Chop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn a recorded golf video into stored, per-swing body data — split both views, run 2D MediaPipe pose on each, auto-detect every swing, segment each swing into 8 phases, and persist swing + pose timelines + phase moments (+ optional annotated clip) to the Batch 0 data store.

**Architecture:** A `vision/` package of small, independently testable modules. A frame-source abstraction (`VideoFileSource`) yields per-frame view crops; pose runs once per frame per view and is cached; `swing_detect` slices the cached timeline into 1..N swing windows from a motion-energy signal; `segment` finds the 8 phases per window; `persist` writes each swing to the store via the existing `store.repo` contract; `pipeline` orchestrates and emits one `SwingResult` per detected swing (live-ready); `run` is the CLI. The only module that changes for future live capture is `frames.py`.

**Tech Stack:** Python 3.12 (at `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`), `opencv-python`, `mediapipe`, `numpy`, `pytest` (dev). Depends on the Batch 0 `store/` package. CPU only.

---

## File Structure

```
vision/
  __init__.py            # package marker
  requirements.txt       # opencv-python, mediapipe, numpy
  constants.py           # ALL tunable thresholds (swing detect + segmentation) in one place
  types.py               # PoseTimeline, FrameSample, SwingWindow, SwingResult dataclasses
  frames.py              # FrameSource interface + VideoFileSource(path, split) -> view crops
  pose.py                # PoseEstimator: one MediaPipe detector per view; bgr -> list[Landmark]
  swing_detect.py        # motion energy -> [SwingWindow, ...] (1..N), stillness-bounded
  segment.py             # one SwingWindow -> list[Moment] (8 phases, confidence-flagged)
  persist.py             # SwingPersister: add_swing + save_pose_frames(both views) + save_moments + save_media
  render.py              # optional annotated per-swing clip (skeleton + phase labels) -> mp4
  pipeline.py            # frames -> pose(both) -> swing_detect -> per swing(segment->persist->render); emits SwingResult
  run.py                 # CLI: python -m vision.run --video <path> --player <name> [--session <id>] ...
  tests/
    __init__.py
    conftest.py          # db fixture (in-memory store) + TEST_VIDEO path + helpers
    test_env.py          # Task 1: cv2 + mediapipe import + construct Pose
    test_frames.py       # split geometry on golf swing.MOV
    test_pose.py         # landmarks on a real frame; empty on no-person frame
    test_swing_detect.py # synthetic motion signals: 1 burst / 3 bursts / fidget
    test_segment.py      # synthetic hand-height curve: 8 phases in order + confidence flag
    test_persist.py      # in-memory store: 2 synthetic swings -> 2 swing rows, both-view pose, 8 moments
    test_render.py       # render writes a non-empty mp4 from synthetic frames
    test_pipeline.py     # smoke on golf swing.MOV: >=1 swing stored w/ both-view pose + moments
```

**Conventions**
- The test video lives at the repo root: `golf swing.MOV`. Tests reference it via `TEST_VIDEO` in `conftest.py` and **skip** (not fail) if it is absent, so unit tests still run on machines without the file.
- Views are keyed `"down_line"` (left half) and `"face_on"` (right half), matching the spec and the `pose_frame.view` column.
- Pose landmark names use MediaPipe's 33-point names (e.g. `left_wrist`, `right_wrist`, `left_shoulder`). The persisted `Landmark` stores pixel `x, y`, normalized-depth `z`, and `visibility`.
- All tunables live in `vision/constants.py`. Tasks reference them by name; never inline a magic number that belongs there.
- Pose inference is nondeterministic across versions/runs — video-derived tests assert **shapes, counts, and ordering with tolerances**, never exact pixel values. Tests on **synthetic** signals (swing_detect, segment) assert exact known results.
- `python` below always means the full path:
  `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`

**Honest limitations (carried from the spec):** the 8-phase 2D heuristics are tuned approximations. `shaft_parallel_down` has no club to measure and is **always** confidence-flagged low. Any phase that cannot be located inside its expected sub-window is emitted with `confidence="low"` rather than guessed silently. All thresholds live in `constants.py` for one-place tuning; expect to adjust them after eyeballing the annotated clip.

---

## Task 1: Environment verification (cv2 + mediapipe on Python 3.12)

**This task gates the whole rock.** MediaPipe wheels for Python 3.12 are not guaranteed. Do not assume the install works — prove it, and if it fails, fall back to a Python 3.11 virtualenv per the documented procedure below before continuing.

**Files:**
- Create: `vision/__init__.py` (empty)
- Create: `vision/requirements.txt`
- Create: `vision/tests/__init__.py` (empty)
- Create: `vision/tests/conftest.py`
- Create: `vision/tests/test_env.py`

- [ ] **Step 1: Create package + requirements**

`vision/__init__.py`: (empty file)

`vision/tests/__init__.py`: (empty file)

`vision/requirements.txt`:
```
opencv-python>=4.8
mediapipe>=0.10
numpy>=1.26,<2.0
```
> NumPy is pinned `<2.0` because mediapipe 0.10.x wheels are built against NumPy 1.x; NumPy 2 triggers ABI errors with several mediapipe builds. Relax only if a known-good mediapipe+NumPy2 combo is confirmed.

- [ ] **Step 2: Create the shared test fixtures**

`vision/tests/conftest.py`:
```python
import os
import pytest
from store import db as dbmod

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEST_VIDEO = os.path.join(REPO_ROOT, "golf swing.MOV")


def has_test_video():
    return os.path.exists(TEST_VIDEO)


requires_video = pytest.mark.skipif(
    not has_test_video(), reason="golf swing.MOV not present at repo root")


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()
```

- [ ] **Step 3: Write the env-verification test**

`vision/tests/test_env.py`:
```python
"""Gate test: proves cv2 + mediapipe import and a Pose detector constructs.

If this fails on Python 3.12, STOP and follow the 3.11 fallback in the plan
(Task 1) before doing anything else.
"""


def test_cv2_imports_and_reads_version():
    import cv2
    assert hasattr(cv2, "__version__")
    assert hasattr(cv2, "VideoCapture")


def test_numpy_is_v1_for_mediapipe_abi():
    import numpy as np
    # mediapipe 0.10.x wheels expect the NumPy 1.x ABI.
    assert np.__version__.split(".")[0] == "1"


def test_mediapipe_imports_and_constructs_pose():
    import mediapipe as mp
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    assert pose is not None
    pose.close()
```

- [ ] **Step 4: Install dependencies**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r vision/requirements.txt
```
Expected: `Successfully installed mediapipe-... opencv-python-... numpy-1...`

- [ ] **Step 5: Run the env test — this is the go/no-go gate**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_env.py -v
```
Expected: **3 passed.**

- [ ] **Step 6 (ONLY if Step 4 or Step 5 fails on 3.12): Python 3.11 fallback**

If `pip install` cannot find a mediapipe wheel, or `test_env.py` fails to import/construct on 3.12, build a dedicated 3.11 virtualenv and use it for **all** subsequent `python` commands in this plan.

1. Confirm Python 3.11 is available (install from python.org if not), then create a venv at the repo root:
   ```
   py -3.11 -m venv .venv311
   ```
   If `py` is not on PATH, use the explicit 3.11 path, e.g.:
   ```
   C:\Users\chris\AppData\Local\Programs\Python\Python311\python.exe -m venv .venv311
   ```
2. Install into the venv (note: `<2.0` NumPy pin still applies):
   ```
   .venv311\Scripts\python.exe -m pip install --upgrade pip
   .venv311\Scripts\python.exe -m pip install -r vision/requirements.txt
   ```
3. Re-run the gate with the venv interpreter:
   ```
   .venv311\Scripts\python.exe -m pytest vision/tests/test_env.py -v
   ```
   Expected: **3 passed.**
4. **From here on, substitute `.venv311\Scripts\python.exe` for every
   `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe` in this
   plan.** Record in the commit message which interpreter won.
   `.venv311/` is already covered by `.gitignore` (`.venv/` pattern — add an
   explicit `.venv311/` line to `.gitignore` if your ignore rules are stricter).

- [ ] **Step 7: Commit**

```bash
git add vision/__init__.py vision/requirements.txt vision/tests/__init__.py vision/tests/conftest.py vision/tests/test_env.py
git commit -m "feat(vision): verify cv2+mediapipe env (Python 3.12 / 3.11 fallback)"
```
> In the commit body, state which interpreter passed the gate (3.12 direct, or `.venv311`).

---

## Task 2: constants.py + types.py (shared tunables and data shapes)

**Files:**
- Create: `vision/constants.py`
- Create: `vision/types.py`
- Test: `vision/tests/test_types.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_types.py`:
```python
def test_constants_present():
    from vision import constants as C
    # swing detection
    assert C.MOTION_SMOOTH_WINDOW >= 1
    assert 0.0 < C.SWING_ENERGY_THRESH_FRAC < 1.0
    assert C.MIN_SWING_FRAMES >= 1
    assert C.MIN_STILL_FRAMES >= 1
    # segmentation
    assert isinstance(C.PHASE_ORDER, tuple)
    assert C.PHASE_ORDER[0] == "address"
    assert C.PHASE_ORDER[-1] == "early_follow_through"
    assert len(C.PHASE_ORDER) == 8


def test_types_construct():
    from vision.types import FrameSample, SwingWindow, SwingResult
    fs = FrameSample(index=0, time_s=0.0,
                     view_crops={"down_line": None, "face_on": None})
    assert fs.index == 0 and "face_on" in fs.view_crops
    w = SwingWindow(start_index=10, end_index=120, peak_index=70)
    assert w.length() == 111
    r = SwingResult(swing_id=1, moments=[], frame_range=(10, 120),
                    view_layout="side_by_side_LR")
    assert r.swing_id == 1 and r.frame_range == (10, 120)
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_types.py -v
```
Expected: FAIL (`vision.constants` / `vision.types` not found).

- [ ] **Step 3: Implement**

`vision/constants.py`:
```python
"""All tunable thresholds for the vision pipeline live here, in ONE place.

These are 2D heuristics tuned against `golf swing.MOV`. Expect to adjust them
after eyeballing the annotated clip. Keep magic numbers out of other modules.
"""

# ---- frame source ----
DEFAULT_SPLIT = 0.5            # fraction of width where left|right views divide
VIEW_DOWN_LINE = "down_line"   # left half
VIEW_FACE_ON = "face_on"       # right half
VIEW_LAYOUT = "side_by_side_LR"

# ---- pose ----
POSE_MODEL_COMPLEXITY = 1
POSE_MIN_DET_CONF = 0.5
POSE_MIN_TRK_CONF = 0.5
LANDMARK_SMOOTH_WINDOW = 5     # moving-average window (frames) for landmark series

# ---- swing detection (motion energy) ----
MOTION_SMOOTH_WINDOW = 5       # moving-average window for the energy signal
# A frame is "in motion" if energy >= this fraction of the per-video peak energy.
SWING_ENERGY_THRESH_FRAC = 0.15
MIN_SWING_FRAMES = 12          # reject motion bursts shorter than this (fidgets)
MIN_STILL_FRAMES = 4           # stillness frames required to close a swing window
# A burst must reach at least this fraction of peak energy to count as a swing.
MIN_PEAK_FRAC = 0.40
SWING_PAD_FRAMES = 3           # pad each window outward by this many frames (clamped)

# ---- segmentation (8 phases) ----
PHASE_ORDER = (
    "address",
    "takeaway",
    "lead_arm_parallel",
    "top",
    "transition",
    "shaft_parallel_down",
    "impact",
    "early_follow_through",
)
# A phase is confidence-flagged low when its locator cannot find a clear feature.
CONF_HIGH = "high"
CONF_LOW = "low"
# shaft_parallel_down has no club to measure -> ALWAYS low confidence.
ALWAYS_LOW_CONF_PHASES = ("shaft_parallel_down",)
# Takeaway: first frame where hand speed exceeds this fraction of window peak speed.
TAKEAWAY_SPEED_FRAC = 0.10
# Lead-arm-parallel / shaft-parallel: |angle to horizontal| within this many deg.
HORIZONTAL_TOL_DEG = 12.0
# Early follow-through: this many frames after impact (clamped to window end).
FOLLOW_THROUGH_FRAMES = 6
# Impact: hands return within this fraction of the address->top hand-height span.
IMPACT_HEIGHT_TOL_FRAC = 0.20

# ---- render ----
RENDER_FOURCC = "mp4v"
SKELETON_THICKNESS = 2
LABEL_FONT_SCALE = 0.7
```

`vision/types.py`:
```python
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from store.models import Landmark, Moment


# A per-frame sample from a frame source: the frame index, its timestamp, and
# the per-view BGR crops. `view_crops` maps view name -> numpy BGR array.
@dataclass
class FrameSample:
    index: int
    time_s: float
    view_crops: Dict[str, object]  # {"down_line": ndarray, "face_on": ndarray}


# The cached pose timeline for ONE view: parallel lists over all frames.
# `frames[i]` is the list[Landmark] for frame i, or None if no pose was found.
@dataclass
class PoseTimeline:
    view: str
    times_s: List[float] = field(default_factory=list)
    frames: List[Optional[List[Landmark]]] = field(default_factory=list)

    def __len__(self):
        return len(self.frames)


# A detected swing: [start_index, end_index] inclusive, plus the peak-energy frame.
@dataclass
class SwingWindow:
    start_index: int
    end_index: int
    peak_index: int

    def length(self):
        return self.end_index - self.start_index + 1


# What the pipeline emits per detected swing (the streaming/live-ready unit).
@dataclass
class SwingResult:
    swing_id: int
    moments: List[Moment]
    frame_range: Tuple[int, int]
    view_layout: str
    media_paths: List[str] = field(default_factory=list)
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_types.py -v
```
Expected: **2 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/constants.py vision/types.py vision/tests/test_types.py
git commit -m "feat(vision): tunable constants + pipeline data types"
```

---

## Task 3: frames.py — frame source + view split

**Files:**
- Create: `vision/frames.py`
- Test: `vision/tests/test_frames.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_frames.py`:
```python
import numpy as np
from vision.frames import split_views, FrameSource, VideoFileSource
from vision import constants as C
from vision.tests.conftest import TEST_VIDEO, requires_video


def test_split_views_geometry_synthetic():
    # 100 wide, 40 tall fake frame; left half|right half at split=0.5
    frame = np.zeros((40, 100, 3), dtype=np.uint8)
    frame[:, :50] = 10   # left
    frame[:, 50:] = 20   # right
    crops = split_views(frame, split=0.5)
    assert set(crops) == {C.VIEW_DOWN_LINE, C.VIEW_FACE_ON}
    assert crops[C.VIEW_DOWN_LINE].shape == (40, 50, 3)
    assert crops[C.VIEW_FACE_ON].shape == (40, 50, 3)
    assert crops[C.VIEW_DOWN_LINE][0, 0, 0] == 10   # left came from left
    assert crops[C.VIEW_FACE_ON][0, 0, 0] == 20     # right came from right


def test_videofilesource_is_a_framesource():
    assert issubclass(VideoFileSource, FrameSource)


@requires_video
def test_videofilesource_yields_monotonic_both_view_crops():
    src = VideoFileSource(TEST_VIDEO, split=0.5)
    assert src.width == 1920 and src.height == 1080
    assert src.fps > 0
    samples = []
    for s in src.frames():
        samples.append(s)
        if len(samples) >= 5:
            break
    src.close()
    # indices and times strictly increasing
    assert [s.index for s in samples] == [0, 1, 2, 3, 4]
    assert all(samples[i].time_s < samples[i + 1].time_s for i in range(4))
    # both views present and each ~half width (960x1080 for the 1920-wide sample)
    for s in samples:
        dl = s.view_crops[C.VIEW_DOWN_LINE]
        fo = s.view_crops[C.VIEW_FACE_ON]
        assert dl.shape[0] == 1080 and fo.shape[0] == 1080
        assert abs(dl.shape[1] - 960) <= 1 and abs(fo.shape[1] - 960) <= 1
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_frames.py -v
```
Expected: FAIL (`vision.frames` not found).

- [ ] **Step 3: Implement**

`vision/frames.py`:
```python
"""Frame source abstraction. VideoFileSource reads a recorded file and yields
per-frame view crops. A future LiveCameraSource implements the same interface
(`frames()` generator of FrameSample), so the rest of the pipeline is unchanged.
"""
import abc
from typing import Dict, Iterator

import cv2

from vision import constants as C
from vision.types import FrameSample


def split_views(frame, split: float = C.DEFAULT_SPLIT) -> Dict[str, object]:
    """Split a side-by-side frame into {down_line: left, face_on: right}."""
    h, w = frame.shape[:2]
    x = int(round(w * split))
    return {
        C.VIEW_DOWN_LINE: frame[:, :x].copy(),
        C.VIEW_FACE_ON: frame[:, x:].copy(),
    }


class FrameSource(abc.ABC):
    """Common interface for recorded and (future) live sources."""

    width: int
    height: int
    fps: float

    @abc.abstractmethod
    def frames(self) -> Iterator[FrameSample]:
        ...

    @abc.abstractmethod
    def close(self) -> None:
        ...


class VideoFileSource(FrameSource):
    def __init__(self, path: str, split: float = C.DEFAULT_SPLIT):
        self.path = path
        self.split = split
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"could not open video: {path}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def frames(self) -> Iterator[FrameSample]:
        index = 0
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            time_s = index / self.fps
            yield FrameSample(index=index, time_s=time_s,
                              view_crops=split_views(frame, self.split))
            index += 1

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_frames.py -v
```
Expected: **3 passed** (or 2 passed + 1 skipped if `golf swing.MOV` is absent).

- [ ] **Step 5: Commit**

```bash
git add vision/frames.py vision/tests/test_frames.py
git commit -m "feat(vision): frame source + side-by-side view split"
```

---

## Task 4: pose.py — MediaPipe pose per view crop

**Files:**
- Create: `vision/pose.py`
- Test: `vision/tests/test_pose.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_pose.py`:
```python
import numpy as np
from vision.pose import PoseEstimator, LANDMARK_NAMES
from vision.frames import VideoFileSource
from vision import constants as C
from vision.tests.conftest import TEST_VIDEO, requires_video


def test_landmark_names_has_33():
    assert len(LANDMARK_NAMES) == 33
    assert "left_wrist" in LANDMARK_NAMES and "right_wrist" in LANDMARK_NAMES


def test_no_person_frame_returns_none():
    est = PoseEstimator(view="face_on")
    blank = np.zeros((300, 200, 3), dtype=np.uint8)  # solid black, no person
    assert est.estimate(blank) is None
    est.close()


@requires_video
def test_pose_on_real_face_on_frame_returns_pixel_landmarks():
    src = VideoFileSource(TEST_VIDEO, split=0.5)
    est = PoseEstimator(view="face_on")
    found = None
    seen = 0
    for s in src.frames():
        crop = s.view_crops[C.VIEW_FACE_ON]
        lms = est.estimate(crop)
        seen += 1
        if lms is not None:
            found = (crop, lms)
            break
        if seen >= 60:   # a person should be visible within the first ~2s
            break
    src.close()
    est.close()
    assert found is not None, "expected pose on at least one early face-on frame"
    crop, lms = found
    assert len(lms) == 33
    h, w = crop.shape[:2]
    # landmarks are in PIXELS of the crop, in range
    for lm in lms:
        assert -1.0 <= lm.x <= w + 1.0
        assert -1.0 <= lm.y <= h + 1.0
        assert 0.0 <= lm.visibility <= 1.0
    names = {lm.name for lm in lms}
    assert "left_wrist" in names and "left_shoulder" in names
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pose.py -v
```
Expected: FAIL (`vision.pose` not found).

- [ ] **Step 3: Implement**

`vision/pose.py`:
```python
"""MediaPipe BlazePose wrapper. One PoseEstimator instance per view. Converts a
BGR crop into a list[Landmark] with PIXEL x,y (of the crop), normalized z, and
visibility. Returns None when no pose is detected (e.g. empty/no-person frame).
"""
from typing import List, Optional

import cv2
import mediapipe as mp

from vision import constants as C
from store.models import Landmark

# MediaPipe Pose 33-landmark names, in landmark-index order.
LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
    "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left",
    "mouth_right", "left_shoulder", "right_shoulder", "left_elbow",
    "right_elbow", "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb", "left_hip",
    "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_foot_index", "right_foot_index",
]


class PoseEstimator:
    def __init__(self, view: str):
        self.view = view
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=C.POSE_MODEL_COMPLEXITY,
            min_detection_confidence=C.POSE_MIN_DET_CONF,
            min_tracking_confidence=C.POSE_MIN_TRK_CONF,
        )

    def estimate(self, bgr) -> Optional[List[Landmark]]:
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if result.pose_landmarks is None:
            return None
        out: List[Landmark] = []
        for i, lm in enumerate(result.pose_landmarks.landmark):
            out.append(Landmark(
                name=LANDMARK_NAMES[i],
                x=lm.x * w,        # normalized -> pixels of the crop
                y=lm.y * h,
                z=lm.z,            # roughly metric-normalized depth (kept as-is)
                visibility=lm.visibility,
            ))
        return out

    def close(self) -> None:
        self._pose.close()
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pose.py -v
```
Expected: **3 passed** (or 2 passed + 1 skipped without the video).

- [ ] **Step 5: Commit**

```bash
git add vision/pose.py vision/tests/test_pose.py
git commit -m "feat(vision): MediaPipe pose per view -> pixel landmarks"
```

---

## Task 5: swing_detect.py — 1..N swing windows from motion energy

This works on a **synthetic** motion signal so the test is deterministic and exact. It does not need pose or video.

**Files:**
- Create: `vision/swing_detect.py`
- Test: `vision/tests/test_swing_detect.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_swing_detect.py`:
```python
import numpy as np
from vision.swing_detect import (
    smooth_signal, motion_energy_from_timeline, detect_swings,
)
from vision.types import PoseTimeline
from store.models import Landmark
from vision import constants as C


def _burst(length, lo=0.0, hi=1.0):
    """A still->motion->still bump as a 1D array of `length`."""
    sig = np.full(length, lo)
    a, b = length // 3, 2 * length // 3
    sig[a:b] = hi
    return sig


def test_smooth_signal_preserves_length():
    sig = np.array([0, 0, 5, 0, 0], dtype=float)
    out = smooth_signal(sig, window=3)
    assert len(out) == len(sig)
    assert out[2] > 0  # peak spread to neighbours


def test_single_burst_one_window():
    # 60 still, 40 high motion, 60 still
    sig = np.concatenate([np.zeros(60), np.ones(40), np.zeros(60)])
    windows = detect_swings(sig)
    assert len(windows) == 1
    w = windows[0]
    # window roughly covers the high stretch [60,100)
    assert 50 <= w.start_index <= 65
    assert 95 <= w.end_index <= 110
    assert 60 <= w.peak_index <= 100


def test_three_bursts_three_windows():
    gap = np.zeros(40)
    pulse = np.ones(30)
    sig = np.concatenate([gap, pulse, gap, pulse, gap, pulse, gap])
    windows = detect_swings(sig)
    assert len(windows) == 3
    starts = [w.start_index for w in windows]
    assert starts == sorted(starts)  # ordered, non-overlapping


def test_fidget_below_min_frames_is_rejected():
    # a tiny 4-frame blip (< MIN_SWING_FRAMES) plus one real swing
    blip = np.zeros(50); blip[20:24] = 1.0
    real = np.zeros(50); real[10:40] = 1.0
    sig = np.concatenate([blip, real])
    windows = detect_swings(sig)
    assert len(windows) == 1  # the blip is rejected, the real swing kept


def test_motion_energy_from_timeline_shape():
    # 5-frame timeline, wrists moving right by 3px/frame
    tl = PoseTimeline(view="face_on")
    for i in range(5):
        tl.times_s.append(i / 30.0)
        tl.frames.append([
            Landmark("left_wrist", 10.0 + 3 * i, 50.0, 0.0, 0.9),
            Landmark("right_wrist", 12.0 + 3 * i, 52.0, 0.0, 0.9),
        ])
    energy = motion_energy_from_timeline(tl)
    assert len(energy) == 5
    assert energy[0] == 0.0          # first frame has no previous -> 0
    assert all(e >= 0 for e in energy)
    assert energy[1] > 0             # motion detected after frame 0
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_swing_detect.py -v
```
Expected: FAIL (`vision.swing_detect` not found).

- [ ] **Step 3: Implement**

`vision/swing_detect.py`:
```python
"""Find 1..N swing windows in a per-frame motion-energy signal. A swing window
is a contiguous high-energy burst flanked by stillness, longer than a minimum
duration and reaching a minimum peak (so fidgets are rejected). The energy
signal is derived from wrist (and overall keypoint) displacement on a cached
pose timeline; tests drive it directly with synthetic signals.
"""
from typing import List, Optional

import numpy as np

from vision import constants as C
from vision.types import PoseTimeline, SwingWindow

_HAND_LANDMARKS = ("left_wrist", "right_wrist", "left_index", "right_index")


def smooth_signal(sig, window: int = C.MOTION_SMOOTH_WINDOW):
    sig = np.asarray(sig, dtype=float)
    if window <= 1 or len(sig) == 0:
        return sig
    kernel = np.ones(window) / window
    return np.convolve(sig, kernel, mode="same")


def _by_name(landmarks):
    return {lm.name: lm for lm in landmarks}


def motion_energy_from_timeline(timeline: PoseTimeline):
    """Per-frame motion energy = mean displacement of hand landmarks from the
    previous frame. Frames with missing pose contribute 0 for that step.
    Returns an array the same length as the timeline; index 0 is 0.0.
    """
    n = len(timeline)
    energy = np.zeros(n, dtype=float)
    prev = None
    for i in range(n):
        cur = timeline.frames[i]
        if cur is not None and prev is not None:
            a, b = _by_name(prev), _by_name(cur)
            disps = []
            for name in _HAND_LANDMARKS:
                if name in a and name in b:
                    dx = b[name].x - a[name].x
                    dy = b[name].y - a[name].y
                    disps.append((dx * dx + dy * dy) ** 0.5)
            if disps:
                energy[i] = float(np.mean(disps))
        if cur is not None:
            prev = cur
    return energy


def detect_swings(energy, *, single_swing: bool = False) -> List[SwingWindow]:
    """Segment a motion-energy signal into swing windows."""
    sig = smooth_signal(energy)
    n = len(sig)
    if n == 0:
        return []
    peak = float(np.max(sig))
    if peak <= 0.0:
        return []

    thresh = peak * C.SWING_ENERGY_THRESH_FRAC
    moving = sig >= thresh

    # collect contiguous moving runs
    runs = []
    i = 0
    while i < n:
        if moving[i]:
            j = i
            while j < n and moving[j]:
                j += 1
            runs.append((i, j - 1))   # inclusive
            i = j
        else:
            i += 1

    # merge runs separated by fewer than MIN_STILL_FRAMES of stillness
    merged = []
    for run in runs:
        if merged and run[0] - merged[-1][1] - 1 < C.MIN_STILL_FRAMES:
            merged[-1] = (merged[-1][0], run[1])
        else:
            merged.append(run)

    windows: List[SwingWindow] = []
    for (s, e) in merged:
        length = e - s + 1
        seg_peak = float(np.max(sig[s:e + 1]))
        if length < C.MIN_SWING_FRAMES:
            continue
        if seg_peak < peak * C.MIN_PEAK_FRAC:
            continue
        s2 = max(0, s - C.SWING_PAD_FRAMES)
        e2 = min(n - 1, e + C.SWING_PAD_FRAMES)
        peak_index = s + int(np.argmax(sig[s:e + 1]))
        windows.append(SwingWindow(start_index=s2, end_index=e2,
                                   peak_index=peak_index))

    if single_swing and windows:
        # keep only the strongest window
        best = max(windows, key=lambda w: sig[w.peak_index])
        windows = [best]
    return windows
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_swing_detect.py -v
```
Expected: **5 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/swing_detect.py vision/tests/test_swing_detect.py
git commit -m "feat(vision): multi-swing detection from motion energy"
```

---

## Task 6: segment.py — 8 phases per swing window (synthetic, exact)

Tested on a **synthetic** hand-height curve with a known shape so phase ordering is exact and deterministic.

**Files:**
- Create: `vision/segment.py`
- Test: `vision/tests/test_segment.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_segment.py`:
```python
import math
from vision.segment import segment_swing
from vision.types import PoseTimeline, SwingWindow
from vision import constants as C
from store.models import Landmark


def _synthetic_swing_timeline(n=120):
    """Build a face-on timeline with a believable swing geometry:
    - hands start low at address (high image-y), rise to the top (low image-y)
    near 40% through, then drop to impact (~address height) near 70%, then rise
    again for follow-through. Lead arm (left shoulder->wrist) sweeps from down,
    through horizontal on the backswing, to up, and back through horizontal on
    the downswing.
    """
    tl = PoseTimeline(view="face_on")
    top = int(n * 0.40)
    impact = int(n * 0.70)
    addr_y = 400.0   # hands low (image y large)
    top_y = 120.0    # hands high (image y small)
    for i in range(n):
        if i <= top:
            frac = i / max(1, top)
            hy = addr_y + (top_y - addr_y) * frac          # rise to top
        elif i <= impact:
            frac = (i - top) / max(1, (impact - top))
            hy = top_y + (addr_y - top_y) * frac           # drop to impact
        else:
            frac = (i - impact) / max(1, (n - 1 - impact))
            hy = addr_y - 120.0 * frac                     # rise past address
        # lead arm: shoulder fixed, wrist sweeps; angle to horizontal varies
        sh_x, sh_y = 300.0, 250.0
        wr_x = sh_x + 80.0 * math.cos(math.radians(20 + 160 * (i / n)))
        tl.times_s.append(i / 120.0)
        tl.frames.append([
            Landmark("left_shoulder", sh_x, sh_y, 0.0, 0.9),
            Landmark("right_shoulder", sh_x + 60, sh_y, 0.0, 0.9),
            Landmark("left_wrist", wr_x, hy, 0.0, 0.9),
            Landmark("right_wrist", wr_x + 10, hy + 5, 0.0, 0.9),
            Landmark("left_hip", sh_x + 5, sh_y + 120, 0.0, 0.9),
            Landmark("right_hip", sh_x + 55, sh_y + 120, 0.0, 0.9),
        ])
    return tl


def test_eight_phases_in_order():
    tl = _synthetic_swing_timeline(120)
    window = SwingWindow(start_index=0, end_index=119, peak_index=84)
    moments = segment_swing(tl, tl, window)  # (down_line, face_on, window)
    kinds = [m.kind for m in moments]
    # all 8 phases present, exactly once, in canonical order
    assert kinds == list(C.PHASE_ORDER)
    idxs = [m.frame_index for m in moments]
    assert idxs == sorted(idxs)            # monotonic frame indices
    assert idxs[0] == window.start_index or idxs[0] >= 0


def test_top_is_highest_hands():
    tl = _synthetic_swing_timeline(120)
    window = SwingWindow(start_index=0, end_index=119, peak_index=84)
    moments = {m.kind: m for m in segment_swing(tl, tl, window)}
    top_idx = moments["top"].frame_index
    # top should land near the 40% mark of the window
    assert abs(top_idx - int(120 * 0.40)) <= 6


def test_low_confidence_flag_for_shaft_parallel_and_missing():
    tl = _synthetic_swing_timeline(120)
    window = SwingWindow(start_index=0, end_index=119, peak_index=84)
    moments = {m.kind: m for m in segment_swing(tl, tl, window)}
    # shaft_parallel_down is club-dependent -> always low confidence
    sp = moments["shaft_parallel_down"]
    assert getattr(sp, "confidence", None) == C.CONF_LOW


def test_missing_pose_window_flags_low_confidence():
    # an all-None timeline: phases can't be found -> emitted, all low-confidence
    tl = PoseTimeline(view="face_on")
    for i in range(40):
        tl.times_s.append(i / 120.0)
        tl.frames.append(None)
    window = SwingWindow(start_index=0, end_index=39, peak_index=20)
    moments = segment_swing(tl, tl, window)
    assert [m.kind for m in moments] == list(C.PHASE_ORDER)
    assert all(getattr(m, "confidence", None) == C.CONF_LOW for m in moments)
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_segment.py -v
```
Expected: FAIL (`vision.segment` not found).

- [ ] **Step 3: Implement**

`vision/segment.py`:
```python
"""Segment ONE swing window into the 8 canonical phases. 2D heuristics over the
cached pose; use the view that reads each phase best (face_on for height/reversal,
down_line for spine/forearm — here both views are passed and face_on drives the
height-based locators). Every phase is emitted exactly once, in canonical order,
with monotonically non-decreasing frame indices. Phases that cannot be located
confidently (or are club-dependent) carry confidence == CONF_LOW.

The returned objects are store.models.Moment instances with an extra
`confidence` attribute attached for the persister to read.
"""
from typing import List, Optional

import numpy as np

from vision import constants as C
from vision.types import PoseTimeline, SwingWindow
from store.models import Moment


def _by_name(landmarks):
    return {lm.name: lm for lm in landmarks} if landmarks else {}


def _hand_y(landmarks):
    """Mean image-y of the wrists (lower y = higher hands). None if missing."""
    d = _by_name(landmarks)
    ys = [d[n].y for n in ("left_wrist", "right_wrist") if n in d]
    return float(np.mean(ys)) if ys else None


def _hand_x(landmarks):
    d = _by_name(landmarks)
    xs = [d[n].x for n in ("left_wrist", "right_wrist") if n in d]
    return float(np.mean(xs)) if xs else None


def _lead_arm_angle_deg(landmarks):
    """Angle of left_shoulder->left_wrist vs horizontal, in degrees [0,90]."""
    d = _by_name(landmarks)
    if "left_shoulder" not in d or "left_wrist" not in d:
        return None
    sh, wr = d["left_shoulder"], d["left_wrist"]
    dx, dy = wr.x - sh.x, wr.y - sh.y
    return abs(math_degrees(dx, dy))


def math_degrees(dx, dy):
    import math
    if dx == 0 and dy == 0:
        return 0.0
    return math.degrees(math.atan2(dy, dx))


def _make_moment(window, kind, view, frame_index, time_s, confidence):
    m = Moment(swing_id=None, kind=kind, view=view,
               frame_index=frame_index, time_s=time_s)
    m.confidence = confidence
    return m


def segment_swing(down_line: PoseTimeline, face_on: PoseTimeline,
                  window: SwingWindow) -> List[Moment]:
    """Return 8 Moment objects (canonical order), each with .confidence."""
    s, e = window.start_index, window.end_index
    n = len(face_on)
    e = min(e, n - 1)
    view = face_on.view

    def t(idx):
        if 0 <= idx < len(face_on.times_s):
            return face_on.times_s[idx]
        return None

    # hand-height series across the window (None where pose missing)
    idxs = list(range(s, e + 1))
    hy = [_hand_y(face_on.frames[i]) for i in idxs]
    have_pose = any(v is not None for v in hy)

    # Helper: index (absolute) of min/max hand-y in a sub-range, ignoring None.
    def extreme(lo, hi, want_min):
        best_idx, best_val = None, None
        for i in range(lo, hi + 1):
            v = _hand_y(face_on.frames[i])
            if v is None:
                continue
            if best_val is None or (v < best_val if want_min else v > best_val):
                best_val, best_idx = v, i
        return best_idx

    results = {}
    confidences = {}

    if not have_pose:
        # No usable pose: spread the 8 phases evenly, all low-confidence.
        span = max(1, e - s)
        for k, name in enumerate(C.PHASE_ORDER):
            fi = s + round(span * k / (len(C.PHASE_ORDER) - 1))
            results[name] = min(e, fi)
            confidences[name] = C.CONF_LOW
        return _ordered_moments(results, confidences, view, t, window)

    # address = window start (last still frame before takeaway)
    results["address"] = s
    confidences["address"] = C.CONF_HIGH

    # top = highest hands (min y) over the whole window
    top_idx = extreme(s, e, want_min=True)
    results["top"] = top_idx if top_idx is not None else s + (e - s) // 2
    confidences["top"] = C.CONF_HIGH if top_idx is not None else C.CONF_LOW

    # takeaway = first frame after address where hand speed exceeds frac of peak
    speeds = []
    for i in range(s, e + 1):
        a = _hand_y(face_on.frames[i - 1]) if i > s else None
        b = _hand_y(face_on.frames[i])
        ax = _hand_x(face_on.frames[i - 1]) if i > s else None
        bx = _hand_x(face_on.frames[i])
        if None in (a, b, ax, bx):
            speeds.append(0.0)
        else:
            speeds.append(((b - a) ** 2 + (bx - ax) ** 2) ** 0.5)
    peak_speed = max(speeds) if speeds else 0.0
    take_idx = None
    if peak_speed > 0:
        thr = peak_speed * C.TAKEAWAY_SPEED_FRAC
        for off, sp in enumerate(speeds):
            if s + off > s and sp >= thr:
                take_idx = s + off
                break
    if take_idx is None or take_idx >= results["top"]:
        take_idx = s + max(1, (results["top"] - s) // 4)
        confidences["takeaway"] = C.CONF_LOW
    else:
        confidences["takeaway"] = C.CONF_HIGH
    results["takeaway"] = take_idx

    # lead_arm_parallel = backswing frame (takeaway..top) closest to horizontal
    lap_idx = _closest_to_horizontal(face_on, take_idx, results["top"])
    if lap_idx is None:
        lap_idx = take_idx + max(1, (results["top"] - take_idx) // 2)
        confidences["lead_arm_parallel"] = C.CONF_LOW
    else:
        confidences["lead_arm_parallel"] = C.CONF_HIGH
    results["lead_arm_parallel"] = lap_idx

    # impact = downswing frame (top..end) where hands return to ~address height
    addr_y = _hand_y(face_on.frames[s])
    top_y = _hand_y(face_on.frames[results["top"]])
    impact_idx = None
    if addr_y is not None and top_y is not None:
        span = abs(addr_y - top_y)
        tol = max(1.0, span * C.IMPACT_HEIGHT_TOL_FRAC)
        for i in range(results["top"] + 1, e + 1):
            v = _hand_y(face_on.frames[i])
            if v is not None and abs(v - addr_y) <= tol:
                impact_idx = i
                break
    if impact_idx is None:
        impact_idx = results["top"] + max(1, (e - results["top"]) * 2 // 3)
        confidences["impact"] = C.CONF_LOW
    else:
        confidences["impact"] = C.CONF_HIGH
    results["impact"] = min(e, impact_idx)

    # transition = first downward hand motion after top
    trans_idx = None
    for i in range(results["top"] + 1, results["impact"] + 1):
        a = _hand_y(face_on.frames[i - 1])
        b = _hand_y(face_on.frames[i])
        if a is not None and b is not None and b > a:  # y increasing => descending
            trans_idx = i
            break
    if trans_idx is None or trans_idx >= results["impact"]:
        trans_idx = results["top"] + max(1, (results["impact"] - results["top"]) // 4)
        confidences["transition"] = C.CONF_LOW
    else:
        confidences["transition"] = C.CONF_HIGH
    results["transition"] = trans_idx

    # shaft_parallel_down = downswing frame (transition..impact) near horizontal
    # ALWAYS low confidence: club-dependent, approximated from lead forearm.
    sp_idx = _closest_to_horizontal(face_on, results["transition"], results["impact"])
    if sp_idx is None:
        sp_idx = results["transition"] + max(
            1, (results["impact"] - results["transition"]) // 2)
    results["shaft_parallel_down"] = sp_idx
    confidences["shaft_parallel_down"] = C.CONF_LOW

    # early_follow_through = fixed interval after impact (clamped)
    eft_idx = min(e, results["impact"] + C.FOLLOW_THROUGH_FRAMES)
    if eft_idx <= results["impact"]:
        eft_idx = min(e, results["impact"] + 1)
    results["early_follow_through"] = eft_idx
    confidences["early_follow_through"] = (
        C.CONF_HIGH if eft_idx > results["impact"] else C.CONF_LOW)

    return _ordered_moments(results, confidences, view, t, window)


def _closest_to_horizontal(timeline: PoseTimeline, lo: int, hi: int) -> Optional[int]:
    """Index in [lo,hi] whose lead-arm angle is closest to horizontal and within
    HORIZONTAL_TOL_DEG; else the closest-to-horizontal index found; None if no
    pose at all in range.
    """
    best_idx, best_err = None, None
    for i in range(lo, hi + 1):
        ang = _lead_arm_angle_deg(timeline.frames[i])
        if ang is None:
            continue
        err = abs(ang)  # 0 deg = horizontal
        if best_err is None or err < best_err:
            best_err, best_idx = err, i
    if best_idx is None:
        return None
    return best_idx


def _ordered_moments(results, confidences, view, t, window) -> List[Moment]:
    """Enforce canonical order + non-decreasing frame indices, build Moments."""
    last = window.start_index
    moments = []
    for name in C.PHASE_ORDER:
        fi = results[name]
        if fi < last:           # enforce monotonic ordering
            fi = last
            confidences[name] = C.CONF_LOW
        # shaft_parallel_down is always low confidence regardless
        if name in C.ALWAYS_LOW_CONF_PHASES:
            confidences[name] = C.CONF_LOW
        fi = min(fi, window.end_index)
        moments.append(_make_moment(window, name, view, fi, t(fi),
                                    confidences[name]))
        last = fi
    return moments
```

> Note: `_lead_arm_angle_deg` returns `abs(atan2(dy,dx))` so 0 deg is horizontal. The `HORIZONTAL_TOL_DEG` constant is the documented tolerance; the current locator always picks the closest-to-horizontal frame and the tolerance is reserved for future confidence gating (kept in `constants.py` so tuning is centralized). This is one of the explicitly approximate 2D heuristics called out in the spec.

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_segment.py -v
```
Expected: **4 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/segment.py vision/tests/test_segment.py
git commit -m "feat(vision): 8-phase segmentation with confidence flags"
```

---

## Task 7: persist.py — write swing + pose (both views) + moments + media

**Files:**
- Create: `vision/persist.py`
- Test: `vision/tests/test_persist.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_persist.py`:
```python
from vision.persist import persist_swing
from vision.types import PoseTimeline, SwingWindow
from vision.segment import segment_swing
from vision import constants as C
from store import repo
from store.models import Landmark, PoseFrame, Moment


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def _timeline(view, n, x0=10.0):
    tl = PoseTimeline(view=view)
    for i in range(n):
        tl.times_s.append(i / 30.0)
        tl.frames.append([
            Landmark("left_wrist", x0 + i, 50.0 + (i % 5), 0.0, 0.9),
            Landmark("right_wrist", x0 + 2 + i, 52.0, 0.0, 0.9),
            Landmark("left_shoulder", 30.0, 40.0, 0.0, 0.9),
        ])
    return tl


def test_persist_one_swing_writes_all_rows(db):
    pid, sid = _ctx(db)
    n = 60
    dl = _timeline(C.VIEW_DOWN_LINE, n)
    fo = _timeline(C.VIEW_FACE_ON, n)
    window = SwingWindow(start_index=10, end_index=49, peak_index=30)
    moments = segment_swing(dl, fo, window)

    swing_id = persist_swing(
        db, player_id=pid, session_id=sid, source_video_path="golf swing.MOV",
        fps=30.0, width=1920, height=1080, view_layout=C.VIEW_LAYOUT,
        down_line=dl, face_on=fo, window=window, moments=moments)

    sw = repo.get_swing(db, swing_id)
    assert sw is not None and sw.player_id == pid and sw.view_layout == C.VIEW_LAYOUT
    # pose frames for BOTH views, only the window range [10,49] -> 40 frames each
    dl_rows = repo.get_pose_frames(db, swing_id, C.VIEW_DOWN_LINE)
    fo_rows = repo.get_pose_frames(db, swing_id, C.VIEW_FACE_ON)
    assert len(dl_rows) == 40 and len(fo_rows) == 40
    assert dl_rows[0].frame_index == 10 and dl_rows[-1].frame_index == 49
    # 8 moments
    saved = repo.get_moments(db, swing_id)
    assert [m.kind for m in saved] == list(C.PHASE_ORDER)


def test_persist_two_swings_independent_rows(db):
    pid, sid = _ctx(db)
    dl = _timeline(C.VIEW_DOWN_LINE, 120)
    fo = _timeline(C.VIEW_FACE_ON, 120)
    w1 = SwingWindow(0, 39, 20)
    w2 = SwingWindow(60, 99, 80)
    id1 = persist_swing(db, player_id=pid, session_id=sid,
                        source_video_path="v.MOV", fps=30.0, width=1920,
                        height=1080, view_layout=C.VIEW_LAYOUT, down_line=dl,
                        face_on=fo, window=w1,
                        moments=segment_swing(dl, fo, w1))
    id2 = persist_swing(db, player_id=pid, session_id=sid,
                        source_video_path="v.MOV", fps=30.0, width=1920,
                        height=1080, view_layout=C.VIEW_LAYOUT, down_line=dl,
                        face_on=fo, window=w2,
                        moments=segment_swing(dl, fo, w2))
    assert id1 != id2
    assert len(repo.list_swings(db, session_id=sid)) == 2
    assert len(repo.get_moments(db, id1)) == 8
    assert len(repo.get_moments(db, id2)) == 8
    assert len(repo.get_pose_frames(db, id1, C.VIEW_FACE_ON)) == 40


def test_persist_media_recorded_when_path_given(db):
    pid, sid = _ctx(db)
    dl = _timeline(C.VIEW_DOWN_LINE, 30)
    fo = _timeline(C.VIEW_FACE_ON, 30)
    w = SwingWindow(0, 29, 15)
    swing_id = persist_swing(
        db, player_id=pid, session_id=sid, source_video_path="v.MOV",
        fps=30.0, width=1920, height=1080, view_layout=C.VIEW_LAYOUT,
        down_line=dl, face_on=fo, window=w, moments=segment_swing(dl, fo, w),
        annotated_path="swings/x/annotated.mp4")
    media = repo.get_media(db, swing_id)
    kinds = {m.kind for m in media}
    assert "source_video" in kinds
    assert "annotated_video" in kinds
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_persist.py -v
```
Expected: FAIL (`vision.persist` not found).

- [ ] **Step 3: Implement**

`vision/persist.py`:
```python
"""Persist ONE detected swing to the Batch 0 store: a swing row, pose_frames for
both views (sliced to the swing window), the 8 moments, and media references
(always the source video; optionally an annotated clip).
"""
from typing import List, Optional

from vision import constants as C
from vision.types import PoseTimeline, SwingWindow
from store import repo
from store.models import PoseFrame, Media, Moment


def _window_pose_frames(swing_id: int, timeline: PoseTimeline,
                        window: SwingWindow) -> List[PoseFrame]:
    frames = []
    e = min(window.end_index, len(timeline) - 1)
    for i in range(window.start_index, e + 1):
        lms = timeline.frames[i]
        if lms is None:
            continue   # skip frames with no pose; the index gap is acceptable
        frames.append(PoseFrame(
            swing_id=swing_id, view=timeline.view, frame_index=i,
            time_s=timeline.times_s[i], landmarks=lms,
            source="mediapipe_pose"))
    return frames


def persist_swing(conn, *, player_id: int, session_id: int,
                  source_video_path: str, fps: float, width: int, height: int,
                  view_layout: str, down_line: PoseTimeline,
                  face_on: PoseTimeline, window: SwingWindow,
                  moments: List[Moment], club: Optional[str] = None,
                  annotated_path: Optional[str] = None) -> int:
    """Write the swing and all its child rows. Returns the new swing id."""
    swing = repo.add_swing(
        conn, session_id, player_id, source_video_path,
        view_layout=view_layout, fps=fps, width=width, height=height, club=club,
        notes=f"frames[{window.start_index}:{window.end_index}]")
    swing_id = swing.id

    dl_frames = _window_pose_frames(swing_id, down_line, window)
    fo_frames = _window_pose_frames(swing_id, face_on, window)
    if dl_frames:
        repo.save_pose_frames(conn, swing_id, C.VIEW_DOWN_LINE, dl_frames)
    if fo_frames:
        repo.save_pose_frames(conn, swing_id, C.VIEW_FACE_ON, fo_frames)

    # stamp swing_id onto the moments (segment leaves it None)
    for m in moments:
        m.swing_id = swing_id
    repo.save_moments(conn, swing_id, moments)

    # media: always record the source video; optionally the annotated clip
    repo.save_media(conn, Media(swing_id=swing_id, kind="source_video",
                                path=source_video_path))
    if annotated_path:
        repo.save_media(conn, Media(swing_id=swing_id, kind="annotated_video",
                                    path=annotated_path))
    return swing_id
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_persist.py -v
```
Expected: **3 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/persist.py vision/tests/test_persist.py
git commit -m "feat(vision): persist swing + both-view pose + moments + media"
```

---

## Task 8: render.py — optional annotated per-swing clip

**Files:**
- Create: `vision/render.py`
- Test: `vision/tests/test_render.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_render.py`:
```python
import os
import numpy as np
from vision.render import render_swing_clip
from vision.types import SwingWindow
from vision import constants as C
from store.models import Landmark, Moment


def _frames(n, h=120, w=160):
    return [np.full((h, w, 3), 30, dtype=np.uint8) for _ in range(n)]


def _pose_list(n):
    out = []
    for i in range(n):
        out.append([
            Landmark("left_shoulder", 40.0, 30.0, 0.0, 0.9),
            Landmark("left_wrist", 40.0 + i, 60.0, 0.0, 0.9),
            Landmark("left_hip", 42.0, 80.0, 0.0, 0.9),
        ])
    return out


def test_render_writes_nonempty_mp4(tmp_path):
    n = 20
    frames = _frames(n)
    poses = _pose_list(n)
    window = SwingWindow(0, n - 1, 10)
    moments = [Moment(swing_id=1, kind="address", view="face_on",
                      frame_index=0, time_s=0.0),
               Moment(swing_id=1, kind="impact", view="face_on",
                      frame_index=14, time_s=0.46)]
    out = os.path.join(str(tmp_path), "annotated.mp4")
    path = render_swing_clip(frames, poses, moments, window, out, fps=30.0)
    assert path == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_render_handles_missing_pose_frames(tmp_path):
    n = 10
    frames = _frames(n)
    poses = [None] * n          # no pose anywhere
    window = SwingWindow(0, n - 1, 5)
    out = os.path.join(str(tmp_path), "a.mp4")
    path = render_swing_clip(frames, poses, [], window, out, fps=30.0)
    assert os.path.exists(path) and os.path.getsize(path) > 0
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_render.py -v
```
Expected: FAIL (`vision.render` not found).

- [ ] **Step 3: Implement**

`vision/render.py`:
```python
"""Optional: draw a per-swing annotated clip (skeleton dots + phase labels) for
immediate review. Saved as an mp4 the persister records as media. Best-effort
overlay — frames without pose are written through unannotated.
"""
import os
from typing import List, Optional

import cv2

from vision import constants as C
from vision.types import SwingWindow
from store.models import Landmark, Moment

# simple skeleton connections by landmark name
_CONNECTIONS = [
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]


def _draw_skeleton(img, landmarks: List[Landmark]):
    by = {lm.name: lm for lm in landmarks}
    for a, b in _CONNECTIONS:
        if a in by and b in by:
            pa = (int(by[a].x), int(by[a].y))
            pb = (int(by[b].x), int(by[b].y))
            cv2.line(img, pa, pb, (0, 255, 0), C.SKELETON_THICKNESS)
    for lm in landmarks:
        cv2.circle(img, (int(lm.x), int(lm.y)), 3, (0, 200, 255), -1)


def render_swing_clip(frames, poses: List[Optional[List[Landmark]]],
                      moments: List[Moment], window: SwingWindow,
                      out_path: str, fps: float = 30.0) -> str:
    """`frames` and `poses` are aligned lists over the swing window (same length).
    Writes an annotated mp4 to out_path and returns out_path.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*C.RENDER_FOURCC)
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    # map absolute frame_index -> phase label for quick lookup
    label_at = {m.frame_index: m.kind for m in moments}
    for offset, img in enumerate(frames):
        canvas = img.copy()
        lms = poses[offset] if offset < len(poses) else None
        if lms:
            _draw_skeleton(canvas, lms)
        abs_idx = window.start_index + offset
        if abs_idx in label_at:
            cv2.putText(canvas, label_at[abs_idx], (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, C.LABEL_FONT_SCALE,
                        (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(canvas)
    writer.release()
    return out_path
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_render.py -v
```
Expected: **2 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/render.py vision/tests/test_render.py
git commit -m "feat(vision): optional annotated per-swing clip"
```

---

## Task 9: pipeline.py — orchestrate frames → pose → detect → per-swing persist; emit SwingResult

**Files:**
- Create: `vision/pipeline.py`
- Test: `vision/tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_pipeline.py`:
```python
from vision.pipeline import build_timelines, process_video
from vision.types import PoseTimeline
from vision import constants as C
from store import repo
from store.models import Landmark
from vision.tests.conftest import TEST_VIDEO, requires_video


class _FakeSource:
    """A frame source that yields synthetic crops without touching disk/OpenCV.
    Lets us test the orchestration without running pose on a real video.
    """
    def __init__(self, n):
        import numpy as np
        self.width, self.height, self.fps = 320, 240, 30.0
        self._n = n
        self._np = np

    def frames(self):
        from vision.types import FrameSample
        for i in range(self._n):
            crop = self._np.zeros((240, 160, 3), dtype=self._np.uint8)
            yield FrameSample(index=i, time_s=i / 30.0,
                              view_crops={C.VIEW_DOWN_LINE: crop,
                                          C.VIEW_FACE_ON: crop})

    def close(self):
        pass


class _FakePose:
    """Pose estimator stub: returns a moving-then-still hand so swing_detect
    finds exactly one window."""
    def __init__(self, view):
        self.view = view

    def estimate(self, bgr):
        # caller increments a counter via closure in the test; here we just
        # return a constant landmark set (motion comes from frame index in test)
        return None  # replaced per-test below


def test_build_timelines_runs_pose_once_per_frame(monkeypatch):
    import numpy as np

    # a pose stub whose hand moves with the frame so energy is nonzero mid-clip
    state = {"i": 0}

    class MovingPose:
        def __init__(self, view):
            self.view = view

        def estimate(self, bgr):
            i = state["i"]
            # hands still for 0..9, moving 10..29, still 30..49
            x = 10.0 + (max(0, min(i - 10, 20)) * 4.0)
            return [Landmark("left_wrist", x, 50.0, 0.0, 0.9),
                    Landmark("right_wrist", x + 2, 52.0, 0.0, 0.9),
                    Landmark("left_shoulder", 30.0, 40.0, 0.0, 0.9)]

    def advance():
        state["i"] += 1

    src = _FakeSource(50)

    # wrap estimate to advance the shared frame counter once per (paired) call
    dl = MovingPose(C.VIEW_DOWN_LINE)
    fo = MovingPose(C.VIEW_FACE_ON)
    orig = fo.estimate

    def fo_estimate(bgr):
        r = orig(bgr)
        advance()
        return r
    fo.estimate = fo_estimate

    down_line, face_on = build_timelines(src, dl, fo)
    assert len(down_line) == 50 and len(face_on) == 50
    assert isinstance(down_line, PoseTimeline)


@requires_video
def test_process_video_smoke_stores_swing(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    results = []
    process_video(db, TEST_VIDEO, player_id=pid, session_id=sid, split=0.5,
                  render=False, on_swing=results.append)
    # at least one swing detected and stored
    swings = repo.list_swings(db, session_id=sid)
    assert len(swings) >= 1
    assert len(results) == len(swings)
    first = swings[0]
    # both views have pose frames
    assert len(repo.get_pose_frames(db, first.id, C.VIEW_DOWN_LINE)) > 0
    assert len(repo.get_pose_frames(db, first.id, C.VIEW_FACE_ON)) > 0
    # 8 moments
    assert len(repo.get_moments(db, first.id)) == 8
    # SwingResult shape
    assert results[0].swing_id == first.id
    assert results[0].view_layout == C.VIEW_LAYOUT
    assert len(results[0].frame_range) == 2
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pipeline.py -v
```
Expected: FAIL (`vision.pipeline` not found).

- [ ] **Step 3: Implement**

`vision/pipeline.py`:
```python
"""Orchestrate the whole rock: frames -> pose(both views, cached) -> swing_detect
-> for each swing(segment -> persist -> optional render). Emits one SwingResult
per swing via the `on_swing` callback as soon as the swing is persisted, so a
future live source yields per-swing data immediately (the spec's immediacy goal).
"""
import os
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from vision import constants as C
from vision.frames import VideoFileSource, FrameSource
from vision.pose import PoseEstimator
from vision.swing_detect import motion_energy_from_timeline, detect_swings
from vision.segment import segment_swing
from vision.persist import persist_swing
from vision.render import render_swing_clip
from vision.types import PoseTimeline, SwingResult


def build_timelines(source: FrameSource, dl_pose, fo_pose):
    """Run pose once per frame per view; return (down_line, face_on) timelines.
    Also caches the raw face_on crops keyed by frame index for optional render.
    """
    down_line = PoseTimeline(view=C.VIEW_DOWN_LINE)
    face_on = PoseTimeline(view=C.VIEW_FACE_ON)
    crops_cache = {}
    for sample in source.frames():
        dl_crop = sample.view_crops[C.VIEW_DOWN_LINE]
        fo_crop = sample.view_crops[C.VIEW_FACE_ON]
        down_line.times_s.append(sample.time_s)
        face_on.times_s.append(sample.time_s)
        down_line.frames.append(dl_pose.estimate(dl_crop))
        face_on.frames.append(fo_pose.estimate(fo_crop))
        crops_cache[sample.index] = fo_crop
    build_timelines.last_crops = crops_cache  # attribute stash for render reuse
    return down_line, face_on


def process_video(conn, video_path: str, *, player_id: int, session_id: int,
                  split: float = C.DEFAULT_SPLIT, single_swing: bool = False,
                  render: bool = False, out_dir: str = "swings",
                  on_swing: Optional[Callable[[SwingResult], None]] = None
                  ) -> List[SwingResult]:
    """Process a recorded video end to end. Returns the list of SwingResults
    (also delivered one-by-one via on_swing as each swing is persisted)."""
    source = VideoFileSource(video_path, split=split)
    dl_pose = PoseEstimator(view=C.VIEW_DOWN_LINE)
    fo_pose = PoseEstimator(view=C.VIEW_FACE_ON)
    results: List[SwingResult] = []
    try:
        down_line, face_on = build_timelines(source, dl_pose, fo_pose)
        crops_cache = getattr(build_timelines, "last_crops", {})

        energy = motion_energy_from_timeline(face_on)
        windows = detect_swings(energy, single_swing=single_swing)
        print(f"[vision] detected {len(windows)} swing(s) in {video_path}")

        for wi, window in enumerate(windows):
            print(f"[vision]   swing {wi}: frames "
                  f"[{window.start_index},{window.end_index}]")
            moments = segment_swing(down_line, face_on, window)

            annotated_path = None
            if render:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                annotated_path = os.path.join(
                    out_dir, f"{stamp}_swing{wi}", "annotated.mp4")
                frames = [crops_cache[i] for i in
                          range(window.start_index, window.end_index + 1)
                          if i in crops_cache]
                poses = [face_on.frames[i] for i in
                         range(window.start_index, window.end_index + 1)
                         if i in crops_cache]
                if frames:
                    render_swing_clip(frames, poses, moments, window,
                                      annotated_path, fps=source.fps)
                else:
                    annotated_path = None

            swing_id = persist_swing(
                conn, player_id=player_id, session_id=session_id,
                source_video_path=video_path, fps=source.fps,
                width=source.width, height=source.height,
                view_layout=C.VIEW_LAYOUT, down_line=down_line, face_on=face_on,
                window=window, moments=moments, annotated_path=annotated_path)

            media_paths = [video_path] + (
                [annotated_path] if annotated_path else [])
            result = SwingResult(
                swing_id=swing_id, moments=moments,
                frame_range=(window.start_index, window.end_index),
                view_layout=C.VIEW_LAYOUT, media_paths=media_paths)
            results.append(result)
            if on_swing is not None:
                on_swing(result)
    finally:
        source.close()
        dl_pose.close()
        fo_pose.close()
    return results
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pipeline.py -v
```
Expected: **2 passed** (or 1 passed + 1 skipped without the video). The smoke
test runs real pose on `golf swing.MOV`; it may take 30-60s on CPU.

- [ ] **Step 5: Commit**

```bash
git add vision/pipeline.py vision/tests/test_pipeline.py
git commit -m "feat(vision): pipeline orchestration emitting per-swing results"
```

---

## Task 10: run.py — CLI entry point

**Files:**
- Create: `vision/run.py`
- Test: `vision/tests/test_run.py`

- [ ] **Step 1: Write the failing test**

`vision/tests/test_run.py`:
```python
from vision.run import build_arg_parser, resolve_player_and_session
from store import repo


def test_arg_parser_defaults_and_required():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "golf swing.MOV", "--player", "Chris"])
    assert args.video == "golf swing.MOV"
    assert args.player == "Chris"
    assert args.split == 0.5
    assert args.session is None
    assert args.render is False
    assert args.single_swing is False
    assert args.height == 72.0


def test_resolve_player_creates_and_reuses(db):
    pid1, sid1 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=None)
    assert pid1 is not None and sid1 is not None
    # second call reuses the same open session + player
    pid2, sid2 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=None)
    assert pid2 == pid1 and sid2 == sid1


def test_resolve_player_honors_explicit_session(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    pid2, sid2 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=sid)
    assert pid2 == pid and sid2 == sid
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_run.py -v
```
Expected: FAIL (`vision.run` not found).

- [ ] **Step 3: Implement**

`vision/run.py`:
```python
"""CLI: process a recorded video into stored per-swing body data.

Usage:
  python -m vision.run --video "golf swing.MOV" --player Chris
  python -m vision.run --video range.mov --player Chris --render
  python -m vision.run --video clip.mov --player Chris --single-swing --session 4
"""
import argparse
import sys

from vision import constants as C
from vision.pipeline import process_video
from store import db as dbmod
from store import repo


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="vision.run",
        description="Video -> stored per-swing body data (pose + 8 phases).")
    p.add_argument("--video", required=True, help="path to the input video")
    p.add_argument("--player", required=True, help="player name (get-or-create)")
    p.add_argument("--height", type=float, default=72.0,
                   help="player height in inches (used when creating the player)")
    p.add_argument("--handedness", default="R", choices=["R", "L"])
    p.add_argument("--session", type=int, default=None,
                   help="existing session id; default reuses/creates an open one")
    p.add_argument("--split", type=float, default=C.DEFAULT_SPLIT,
                   help="fraction of width dividing left|right views")
    p.add_argument("--single-swing", dest="single_swing", action="store_true",
                   help="force exactly one swing (strongest window)")
    p.add_argument("--render", action="store_true",
                   help="also write an annotated clip per swing")
    p.add_argument("--out", default="swings", help="output dir for clips")
    p.add_argument("--db", default=None, help="sqlite path (default app DB)")
    return p


def resolve_player_and_session(conn, *, player, height_in, handedness,
                               session_id):
    pid = repo.get_or_create_player(conn, player, height_in, handedness).id
    if session_id is not None:
        return pid, session_id
    open_sess = repo.get_open_session(conn, pid)
    if open_sess is not None:
        return pid, open_sess.id
    return pid, repo.create_session(conn, pid).id


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn=conn)
    pid, sid = resolve_player_and_session(
        conn, player=args.player, height_in=args.height,
        handedness=args.handedness, session_id=args.session)

    def on_swing(result):
        print(f"[vision] stored swing id={result.swing_id} "
              f"frames={result.frame_range} moments={len(result.moments)}")

    results = process_video(
        conn, args.video, player_id=pid, session_id=sid, split=args.split,
        single_swing=args.single_swing, render=args.render, out_dir=args.out,
        on_swing=on_swing)
    print(f"[vision] done: {len(results)} swing(s) stored for player_id={pid}, "
          f"session_id={sid}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_run.py -v
```
Expected: **3 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/run.py vision/tests/test_run.py
git commit -m "feat(vision): CLI entry point (player/session resolution)"
```

---

## Task 11: Full-suite green + end-to-end manual run + regression lock

**Files:**
- Modify: `vision/tests/test_pipeline.py` (append a regression-count assertion)

- [ ] **Step 1: Run the entire vision suite**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/ -v
```
Expected: all tests **pass** (video-dependent tests pass if `golf swing.MOV`
present, else skipped). Also confirm the store suite is unaffected:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ vision/ -q
```

- [ ] **Step 2: Real end-to-end CLI run with render (manual eyeball)**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m vision.run --video "golf swing.MOV" --player Chris --render --single-swing
```
Expected console: a detected-swing count, one or more `stored swing id=...`
lines, and a final `done: N swing(s) stored` line. Open the written
`swings/<stamp>_swing0/annotated.mp4` and verify the skeleton tracks the body
and the 8 phase labels appear in the correct order. Note: this is the human
validation gate the spec requires before locking a regression count.

> `golf swing.MOV` is a single-swing clip, so `--single-swing` is appropriate
> here. Drop it for true range videos.

- [ ] **Step 3: Lock the swing count as a regression check**

After eyeballing, record the observed swing count for the sample clip. Append to
`vision/tests/test_pipeline.py`:
```python
@requires_video
def test_golf_swing_mov_detects_expected_count(db):
    """Regression lock: golf swing.MOV is a single dominant swing. With the
    default (multi-swing) detector it yields exactly one window; assert it so a
    threshold change that splits/merges swings is caught.
    """
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    results = process_video(db, TEST_VIDEO, player_id=pid, session_id=sid,
                            render=False)
    # EXPECTED count for the sample clip — adjust ONLY after re-eyeballing.
    assert len(results) == 1
    r = results[0]
    # the swing should span a plausible chunk of the ~560-frame clip
    start, end = r.frame_range
    assert end - start >= C.MIN_SWING_FRAMES
```
> If Step 2 shows a different count for this clip (e.g. detector tuning yields 2),
> set the asserted number to the eyeballed truth and note why in the commit. This
> is the intended human-in-the-loop calibration point.

- [ ] **Step 4: Re-run to confirm the regression test passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pipeline.py -v
```
Expected: **pass** (including the new regression test) or skipped without video.

- [ ] **Step 5: Commit**

```bash
git add vision/tests/test_pipeline.py
git commit -m "test(vision): lock golf swing.MOV swing-count regression"
```

---

## Done criteria

- `python -m pytest store/ vision/ -q` is fully green (video-dependent tests pass
  with `golf swing.MOV` present, else skipped — never failed).
- The env gate (Task 1) passed on Python 3.12, or the documented 3.11 venv was
  built and used for every subsequent command.
- `python -m vision.run --video "golf swing.MOV" --player Chris --render` stores
  >=1 swing with both-view pose frames + 8 moments, and writes a viewable
  annotated clip whose skeleton and phase labels were eyeballed once.
- Every module in the spec's table exists under `vision/`: `frames`, `pose`,
  `swing_detect`, `segment`, `persist`, `render`, `pipeline`, `run` (plus
  `constants` and `types`), each independently tested.
- All tunable thresholds live in `vision/constants.py`. The known-approximate 2D
  heuristics (`shaft_parallel_down` and any unlocatable phase) are stored with a
  low-confidence flag rather than guessed silently, exactly as the spec demands.
```
