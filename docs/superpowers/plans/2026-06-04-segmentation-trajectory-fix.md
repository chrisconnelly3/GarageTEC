# Swing Segmentation Fix — Continuous Hand-Position-Trajectory Approach

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the motion-energy swing detector in `vision/swing_detect.py` with a **continuous hand-position-trajectory** detector that is robust to mid-swing pauses (top-of-backswing dwell AND lag-artifact freezes). A swing is one *excursion-and-return*: the hands depart a stable address rest region, rise to an apex (top of backswing), fall back through address height, follow through, and only then **return to the address rest region and stay there** for a sustained minimum duration. Boundaries are declared on *sustained return to address*, never on motion gaps — so a momentary dwell mid-swing can never split one swing into many.

**The bug being fixed:** The current detector treats a swing as "a burst of MOTION ENERGY between two stretches of stillness." A golf swing has a brief genuine pause at the top of the backswing, and our stress-test clip (`golf swing.MOV`, recorded on a laggy PC) additionally has random lag-artifact freezes. Both kinds of pause look like "stillness" to the motion-burst detector, which therefore splits the ONE physical swing into ~4 windows (observed default ranges `[208,241] [329,369] [378,422] [435,471]`, locked today in `test_golf_swing_mov_detects_expected_count`). Real GarageTEC recordings will be smooth, continuous video with no artifact pauses — we design defaults for the smooth case, but the algorithm must absorb pauses generically (no special-casing the artifact). The stress-test clip must resolve to **exactly 1 swing**.

**Architecture (what changes vs. what does not):** Only the *swing-finding* stage changes. The contract with the rest of the pipeline is preserved exactly:
- `detect_swings(signal, *, single_swing=False) -> List[SwingWindow]` keeps its name, return type, and `single_swing` keyword — but `signal` is now a **1-D hand-position (height) trajectory** instead of a motion-energy array.
- A new builder `hand_trajectory_from_timeline(timeline) -> np.ndarray` replaces `motion_energy_from_timeline` as the signal source (the old function is **removed**; nothing else consumes it).
- `SwingWindow(start_index, end_index, peak_index)` is **unchanged** — `peak_index` is now the apex frame (top of backswing = min image-y / max height) instead of the peak-energy frame. `segment.py` only reads `start_index`/`end_index` from the window (it recomputes `top` itself), so this is fully drop-in; `segment.py` is **not modified**.
- `pipeline.py` changes two lines: import + call `hand_trajectory_from_timeline` instead of `motion_energy_from_timeline`.
- `types.py` is unchanged. All new tunables go in `vision/constants.py`.

**Tech Stack:** Python 3.12 at `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe` (mediapipe + opencv-python + numpy already installed; no new deps). `pytest` for tests. Depends on the Batch 0 `store/` package.

---

## File Structure

```
vision/
  constants.py            # MODIFY: remove motion-energy tunables, add trajectory tunables
  swing_detect.py         # REWRITE: hand-trajectory signal + excursion/return detector
  pipeline.py             # MODIFY (2 lines): use hand_trajectory_from_timeline
  types.py                # UNCHANGED (SwingWindow contract preserved)
  segment.py              # UNCHANGED (reads only start/end of the window)
  tests/
    test_swing_detect.py  # REWRITE: synthetic trajectory tests (known answers)
    test_pipeline.py      # MODIFY: replace the over-split count lock (4) with ==1
```

**Conventions**
- `python` below always means the full path
  `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`. The `py` launcher is **not** on PATH — never use it.
- The test video lives at the repo root: `golf swing.MOV` (1080p, ~30 fps, side-by-side LEFT=down-line | RIGHT=face-on, ONE physical swing). Tests reference it via `TEST_VIDEO` in `vision/tests/conftest.py` and **skip** (never fail) when absent, via the existing `requires_video` marker.
- The detector runs on the **face-on** view (RIGHT half), the same view `swing_detect` + `segment` use today. Height = mean image-y of `left_wrist` + `right_wrist`. In image coordinates **smaller y = higher hands**; the apex (top of backswing) is the **minimum** of the height signal.
- Synthetic-signal tests assert **exact** known results. The single real-video test asserts a **count with a human-eyeball note**, never pixel values.
- All tunables live in `vision/constants.py`; never inline a magic number that belongs there.

**Algorithm (the design this plan builds):**
1. **Signal.** Per frame, hand-center height = mean of lead+trail wrist `y` on the face-on timeline. Missing-pose frames are filled by linear interpolation between known neighbours (hold at the ends). Then smooth with a centered moving-average / median window wide enough to absorb jitter **and** brief freezes. The result is a continuous 1-D trajectory `h[i]`.
2. **Address rest region.** Find the calm setup at the start: the sustained low-movement stretch whose median height defines `addr_level`. The "rest region" is `|h[i] - addr_level| <= ADDRESS_REGION_RADIUS` (radius is a fraction of the swing's vertical span, computed from the signal).
3. **Excursion.** A swing begins when the hands **depart** the rest region (leave the band around `addr_level`) and reach an **apex** — the maximum departure (min y) — that exceeds a minimum amplitude. The apex frame is the SwingWindow `peak_index`.
4. **Sustained return (the core fix).** A swing **ends** only when the hands come back **inside** the rest region AND stay there continuously for at least `MIN_RETURN_FRAMES` (≈0.7–1.0 s worth of frames). A momentary dwell/freeze mid-swing keeps the hands **away** from the rest region (they are up near the apex or mid-descent, not at address), so it never satisfies the sustained-return test and never creates a boundary. **No boundary is ever declared on a motion gap.**
5. **Multi-swing & rejection.** Each depart → apex → sustained-return cycle is one swing. Excursions whose amplitude `< MIN_SWING_AMPLITUDE_FRAC` of span, or whose duration `< MIN_SWING_FRAMES`, are rejected as fidgets/waggles.
6. **Output.** Same `SwingWindow(start_index, end_index, peak_index)` list `segment.py` expects (padded by `SWING_PAD_FRAMES`, clamped to `[0, n-1]`). `single_swing=True` keeps only the largest-amplitude window.

---

## Task 1: constants.py — swap motion-energy tunables for trajectory tunables

**Files:**
- Modify: `vision/constants.py`

- [ ] **Step 1: Write the failing test (new tunables present, old ones gone)**

Append to `vision/tests/test_swing_detect.py` is done in Task 2; for *this* task, add a focused constants assertion to the existing `vision/tests/test_types.py`. Open `vision/tests/test_types.py` and **replace** the body of `test_constants_present` with:

```python
def test_constants_present():
    from vision import constants as C
    # ---- swing detection (hand-position trajectory) ----
    assert C.TRAJ_SMOOTH_WINDOW >= 1
    assert 0.0 < C.ADDRESS_REGION_RADIUS_FRAC < 1.0
    assert C.ADDRESS_REST_FRAMES >= 1
    assert C.MIN_RETURN_FRAMES >= 1
    assert 0.0 < C.MIN_SWING_AMPLITUDE_FRAC < 1.0
    assert C.MIN_SWING_FRAMES >= 1
    assert C.SWING_PAD_FRAMES >= 0
    # the old motion-energy knobs must be gone
    assert not hasattr(C, "MOTION_SMOOTH_WINDOW")
    assert not hasattr(C, "SWING_ENERGY_THRESH_FRAC")
    assert not hasattr(C, "MIN_STILL_FRAMES")
    assert not hasattr(C, "MIN_PEAK_FRAC")
    # segmentation block is untouched
    assert isinstance(C.PHASE_ORDER, tuple)
    assert C.PHASE_ORDER[0] == "address"
    assert C.PHASE_ORDER[-1] == "early_follow_through"
    assert len(C.PHASE_ORDER) == 8
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_types.py::test_constants_present -v
```
Expected: FAIL (`AttributeError: module 'vision.constants' has no attribute 'TRAJ_SMOOTH_WINDOW'`).

- [ ] **Step 3: Implement — edit the swing-detection block in `vision/constants.py`**

Find the existing block:
```python
# ---- swing detection (motion energy) ----
MOTION_SMOOTH_WINDOW = 5       # moving-average window for the energy signal
# A frame is "in motion" if energy >= this fraction of the per-video peak energy.
SWING_ENERGY_THRESH_FRAC = 0.15
MIN_SWING_FRAMES = 12          # reject motion bursts shorter than this (fidgets)
MIN_STILL_FRAMES = 4           # stillness frames required to close a swing window
# A burst must reach at least this fraction of peak energy to count as a swing.
MIN_PEAK_FRAC = 0.40
SWING_PAD_FRAMES = 3           # pad each window outward by this many frames (clamped)
```

and **replace it entirely** with:
```python
# ---- swing detection (hand-position trajectory) ----
# A swing is ONE excursion-and-return of the hands away from the address rest
# region, NOT a burst of motion. A boundary is declared only when the hands
# RETURN to the address region and STAY there for a sustained minimum duration,
# so a mid-swing pause (top-of-backswing dwell or a lag-artifact freeze) can
# never split one swing. Defaults are tuned for SMOOTH ~30 fps video.

# Centered moving-average window (frames) applied to the hand-height trajectory.
# Wide enough to absorb jitter AND brief freezes without erasing the swing arc.
TRAJ_SMOOTH_WINDOW = 7
# The address rest region is |h - addr_level| <= ADDRESS_REGION_RADIUS_FRAC * span,
# where `span` is the full vertical travel of the smoothed signal. Hands inside
# this band count as "at address".
ADDRESS_REGION_RADIUS_FRAC = 0.18
# Frames of sustained low movement required at the START to lock the address
# level (the calm setup). Short relative to a swing.
ADDRESS_REST_FRAMES = 8
# THE CORE FIX: hands must sit inside the address region continuously for at
# least this many frames before a swing boundary is declared. ~0.8 s @ 30 fps.
# A momentary dwell mid-swing keeps the hands AWAY from address, so it never
# reaches this threshold and never triggers a boundary.
MIN_RETURN_FRAMES = 24
# An excursion must reach at least this fraction of the signal's full vertical
# span to count as a swing (rejects fidgets / waggles below it).
MIN_SWING_AMPLITUDE_FRAC = 0.35
# Reject excursions shorter than this many frames (fidgets).
MIN_SWING_FRAMES = 12
# Pad each window outward by this many frames (clamped to the signal bounds).
SWING_PAD_FRAMES = 3
```

> Keep `LANDMARK_SMOOTH_WINDOW`, the `# ---- segmentation (8 phases) ----` block, and the `# ---- render ----` block exactly as they are. `MIN_SWING_FRAMES` and `SWING_PAD_FRAMES` survive (same names, same role); the four energy-specific knobs are removed.

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_types.py -v
```
Expected: **2 passed.**

- [ ] **Step 5: Commit**

```bash
git add vision/constants.py vision/tests/test_types.py
git commit -m "feat(vision): trajectory tunables replace motion-energy knobs"
```

---

## Task 2: swing_detect.py — rewrite as a hand-trajectory excursion/return detector

This is the heart of the fix. It works on a **synthetic** 1-D height trajectory so the tests are deterministic and exact — no pose or video needed. The `hand_trajectory_from_timeline` builder is exercised with a tiny synthetic `PoseTimeline`, including a missing-pose gap.

**Files:**
- Rewrite: `vision/swing_detect.py`
- Rewrite: `vision/tests/test_swing_detect.py`

- [ ] **Step 1: Write the failing tests**

**Replace the entire contents** of `vision/tests/test_swing_detect.py` with:

```python
"""Synthetic-trajectory tests for the hand-position swing detector.

The detector consumes a 1-D HAND-HEIGHT trajectory (mean wrist image-y; smaller
y = higher hands). A swing is one excursion away from the address rest region up
to an apex (min y) and back, with the boundary declared only on a SUSTAINED
return to address. These tests build trajectories with known answers; the
critical regression is `test_mid_swing_dwell_stays_one_window` (a flat freeze in
the middle of a single arc must NOT split it).
"""
import numpy as np
from vision.swing_detect import (
    smooth_signal, hand_trajectory_from_timeline, detect_swings,
)
from vision.types import PoseTimeline
from store.models import Landmark
from vision import constants as C


# ---- trajectory builders (image-y: address HIGH value, apex LOW value) --------

ADDR = 400.0      # hands low at address -> large image-y
APEX = 120.0      # hands high at top    -> small image-y


def _rest(n):
    """`n` frames sitting at the address level (with negligible jitter)."""
    return np.full(n, ADDR, dtype=float)


def _arc(n_up, n_down, apex=APEX, addr=ADDR):
    """One excursion: rise addr->apex over n_up frames, fall apex->addr over
    n_down. Starts and ends AT address but never dwells there mid-arc."""
    up = np.linspace(addr, apex, n_up, endpoint=False)
    down = np.linspace(apex, addr, n_down)
    return np.concatenate([up, down])


def test_smooth_signal_preserves_length():
    sig = np.array([0, 0, 5, 0, 0], dtype=float)
    out = smooth_signal(sig, window=3)
    assert len(out) == len(sig)


def test_single_clean_arc_one_window():
    # rest -> one arc -> sustained rest
    sig = np.concatenate([
        _rest(C.ADDRESS_REST_FRAMES + 5),
        _arc(30, 30),
        _rest(C.MIN_RETURN_FRAMES + 10),
    ])
    windows = detect_swings(sig)
    assert len(windows) == 1
    w = windows[0]
    # apex (min y) sits inside the window
    assert w.start_index <= w.peak_index <= w.end_index
    assert sig[w.peak_index] < ADDR - 100  # genuinely up near the apex


def test_three_arcs_separated_by_sustained_returns_three_windows():
    rest_lead = _rest(C.ADDRESS_REST_FRAMES + 5)
    rest_gap = _rest(C.MIN_RETURN_FRAMES + 8)   # sustained -> a real boundary
    sig = np.concatenate([
        rest_lead,
        _arc(25, 25), rest_gap,
        _arc(25, 25), rest_gap,
        _arc(25, 25), _rest(C.MIN_RETURN_FRAMES + 8),
    ])
    windows = detect_swings(sig)
    assert len(windows) == 3
    starts = [w.start_index for w in windows]
    assert starts == sorted(starts)            # ordered, non-overlapping


def test_mid_swing_dwell_stays_one_window():
    """THE CRITICAL REGRESSION. One arc with a flat DWELL in the middle (mimics
    the top-of-backswing pause / lag-artifact freeze). The dwell holds the hands
    UP near the apex (away from address), so the sustained-return boundary never
    fires and the arc stays a SINGLE window — the over-split is cured.
    """
    dwell = np.full(C.MIN_RETURN_FRAMES + 15, APEX)   # long freeze, but UP top
    sig = np.concatenate([
        _rest(C.ADDRESS_REST_FRAMES + 5),
        np.linspace(ADDR, APEX, 25, endpoint=False),  # backswing up to apex
        dwell,                                         # <-- mid-swing freeze
        np.linspace(APEX, ADDR, 25),                  # downswing back to addr
        _rest(C.MIN_RETURN_FRAMES + 10),
    ])
    windows = detect_swings(sig)
    assert len(windows) == 1, (
        "a mid-swing dwell at the apex must NOT create a swing boundary")
    w = windows[0]
    # the window spans across the dwell (start before it, end after it)
    dwell_mid = C.ADDRESS_REST_FRAMES + 5 + 25 + len(dwell) // 2
    assert w.start_index < dwell_mid < w.end_index


def test_fidget_below_amplitude_is_rejected():
    # a small waggle: amplitude far below MIN_SWING_AMPLITUDE_FRAC of the span
    waggle = np.concatenate([_arc(6, 6, apex=ADDR - 20)])  # only 20px up
    sig = np.concatenate([
        _rest(C.ADDRESS_REST_FRAMES + 5),
        waggle,
        _rest(C.MIN_RETURN_FRAMES + 5),
        _arc(30, 30),                       # one real swing to set the span
        _rest(C.MIN_RETURN_FRAMES + 5),
    ])
    windows = detect_swings(sig)
    assert len(windows) == 1                # waggle rejected, real swing kept


def test_pure_fidget_only_zero_windows():
    # nothing but tiny waggles -> no swing at all
    sig = np.concatenate([
        _rest(C.ADDRESS_REST_FRAMES + 5),
        _arc(6, 6, apex=ADDR - 15),
        _rest(10),
        _arc(6, 6, apex=ADDR - 15),
        _rest(C.MIN_RETURN_FRAMES + 5),
    ])
    assert detect_swings(sig) == []


def test_single_swing_flag_keeps_largest_excursion():
    sig = np.concatenate([
        _rest(C.ADDRESS_REST_FRAMES + 5),
        _arc(20, 20, apex=ADDR - 150),       # smaller arc
        _rest(C.MIN_RETURN_FRAMES + 8),
        _arc(30, 30, apex=APEX),             # larger arc (full span)
        _rest(C.MIN_RETURN_FRAMES + 8),
    ])
    multi = detect_swings(sig)
    assert len(multi) == 2
    single = detect_swings(sig, single_swing=True)
    assert len(single) == 1
    # the kept window is the larger-amplitude (deeper apex) one
    assert sig[single[0].peak_index] <= sig[multi[0].peak_index]


# ---- the timeline builder (signal source) ------------------------------------

def test_hand_trajectory_from_timeline_basic():
    tl = PoseTimeline(view="face_on")
    for i in range(5):
        tl.times_s.append(i / 30.0)
        tl.frames.append([
            Landmark("left_wrist", 10.0, 50.0 + 4 * i, 0.0, 0.9),
            Landmark("right_wrist", 12.0, 52.0 + 4 * i, 0.0, 0.9),
        ])
    traj = hand_trajectory_from_timeline(tl)
    assert len(traj) == 5
    # mean wrist-y increases frame to frame (raw, before smoothing checks)
    assert traj[0] < traj[-1]


def test_hand_trajectory_interpolates_missing_pose():
    # frame 2 has no pose -> value is interpolated, not NaN, no crash
    tl = PoseTimeline(view="face_on")
    ys = [100.0, 110.0, None, 130.0, 140.0]
    for i, y in enumerate(ys):
        tl.times_s.append(i / 30.0)
        if y is None:
            tl.frames.append(None)
        else:
            tl.frames.append([
                Landmark("left_wrist", 10.0, y, 0.0, 0.9),
                Landmark("right_wrist", 12.0, y, 0.0, 0.9),
            ])
    traj = hand_trajectory_from_timeline(tl)
    assert len(traj) == 5
    assert np.all(np.isfinite(traj))         # no NaN survived
    assert 110.0 <= traj[2] <= 130.0         # interpolated between neighbours


def test_all_missing_pose_does_not_crash():
    tl = PoseTimeline(view="face_on")
    for i in range(10):
        tl.times_s.append(i / 30.0)
        tl.frames.append(None)
    traj = hand_trajectory_from_timeline(tl)
    assert len(traj) == 10
    assert np.all(np.isfinite(traj))         # filled with a constant, finite
    assert detect_swings(traj) == []         # flat -> no swing, no crash
```

- [ ] **Step 2: Run to verify it fails**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_swing_detect.py -v
```
Expected: FAIL — `ImportError: cannot import name 'hand_trajectory_from_timeline'` (the rewrite does not exist yet). This proves the new tests drive the new code.

- [ ] **Step 3: Implement — replace the entire contents of `vision/swing_detect.py`**

```python
"""Detect 1..N swings from a CONTINUOUS hand-position trajectory.

A swing is ONE excursion-and-return: the hands DEPART the address rest region,
rise to an apex (top of backswing = minimum image-y), fall back through address
height, follow through, and eventually RETURN to the address region and STAY
there for a sustained minimum duration. A swing boundary is declared ONLY on
that sustained return -- never on a motion gap. A momentary dwell/freeze
mid-swing (top-of-backswing pause or lag-artifact) holds the hands AWAY from
address, so it can never satisfy the sustained-return test and never splits a
swing. This is what cures the over-split the old motion-energy detector caused.

The signal is the mean wrist image-y on the face-on timeline (smaller y = higher
hands). Missing-pose frames are interpolated. Tests drive `detect_swings`
directly with synthetic trajectories.
"""
from typing import List, Optional

import numpy as np

from vision import constants as C
from vision.types import PoseTimeline, SwingWindow

_WRIST_LANDMARKS = ("left_wrist", "right_wrist")


def smooth_signal(sig, window: int = C.TRAJ_SMOOTH_WINDOW):
    """Centered moving average that preserves length and absorbs brief freezes."""
    sig = np.asarray(sig, dtype=float)
    if window <= 1 or len(sig) == 0:
        return sig
    kernel = np.ones(window) / window
    return np.convolve(sig, kernel, mode="same")


def _by_name(landmarks):
    return {lm.name: lm for lm in landmarks} if landmarks else {}


def _hand_y(landmarks) -> Optional[float]:
    """Mean image-y of the wrists for one frame, or None if unavailable."""
    d = _by_name(landmarks)
    ys = [d[n].y for n in _WRIST_LANDMARKS if n in d]
    return float(np.mean(ys)) if ys else None


def _interpolate_missing(raw: List[Optional[float]]) -> np.ndarray:
    """Fill None entries by linear interpolation between known neighbours;
    hold the nearest known value at the ends. All-None -> all zeros."""
    n = len(raw)
    out = np.zeros(n, dtype=float)
    known_i = [i for i, v in enumerate(raw) if v is not None]
    if not known_i:
        return out                      # no pose at all -> flat zero signal
    known_v = np.array([raw[i] for i in known_i], dtype=float)
    all_i = np.arange(n)
    out = np.interp(all_i, known_i, known_v)  # holds ends, linear between
    return out


def hand_trajectory_from_timeline(timeline: PoseTimeline) -> np.ndarray:
    """Build the per-frame hand-height trajectory (mean wrist image-y), with
    missing-pose frames interpolated. Returns a finite float array of len(timeline).
    """
    raw = [_hand_y(timeline.frames[i]) for i in range(len(timeline))]
    return _interpolate_missing(raw)


def _address_level(sig: np.ndarray) -> float:
    """The address rest level: median height over the calm setup stretch at the
    start. Falls back to the global median if the clip is too short."""
    k = min(len(sig), max(1, C.ADDRESS_REST_FRAMES))
    return float(np.median(sig[:k]))


def detect_swings(signal, *, single_swing: bool = False) -> List[SwingWindow]:
    """Segment a hand-height trajectory into swing windows.

    `signal` is a 1-D array of mean wrist image-y per frame (smaller = higher).
    Returns SwingWindow(start_index, end_index, peak_index) where peak_index is
    the apex frame (min y). `single_swing=True` keeps only the largest excursion.
    """
    sig = smooth_signal(signal)
    n = len(sig)
    if n == 0:
        return []

    addr = _address_level(sig)
    span = float(np.max(sig) - np.min(sig))
    if span <= 0.0:
        return []                       # perfectly flat -> nothing happened

    radius = span * C.ADDRESS_REGION_RADIUS_FRAC
    # "at address" = within the radius band around the address level. The apex
    # is ABOVE address (smaller y), so departure means h < addr - radius.
    at_address = np.abs(sig - addr) <= radius

    min_amp = span * C.MIN_SWING_AMPLITUDE_FRAC

    windows: List[SwingWindow] = []
    i = 0
    while i < n:
        # advance to the first frame the hands are clearly AT address, then to
        # the first DEPARTURE from the address region.
        # find a departure: a run leaving the address band heading upward.
        if at_address[i]:
            i += 1
            continue

        # i is outside the address band -> a candidate excursion starts here.
        start = i
        # walk forward until the hands RETURN to address and STAY for
        # MIN_RETURN_FRAMES consecutive frames (the sustained-return boundary).
        j = i
        end = None
        while j < n:
            if at_address[j]:
                # count how long they stay inside the band from here
                k = j
                while k < n and at_address[k]:
                    k += 1
                dwell = k - j
                if dwell >= C.MIN_RETURN_FRAMES or k >= n:
                    # sustained return (or we hit the clip end) -> boundary.
                    end = j          # boundary at first frame back at address
                    j = k
                    break
                # brief touch of the address band that is NOT sustained: this is
                # not a real boundary (e.g. passing through address at impact).
                # keep going INSIDE the same excursion.
                j = k
            else:
                j += 1
        if end is None:
            end = n - 1              # ran off the end still away from address

        # measure the excursion: apex = min y (highest hands) in [start, end].
        seg = sig[start:end + 1]
        apex_off = int(np.argmin(seg))
        apex_idx = start + apex_off
        amplitude = addr - float(sig[apex_idx])   # how far above address
        length = end - start + 1

        if amplitude >= min_amp and length >= C.MIN_SWING_FRAMES:
            s2 = max(0, start - C.SWING_PAD_FRAMES)
            e2 = min(n - 1, end + C.SWING_PAD_FRAMES)
            windows.append(SwingWindow(start_index=s2, end_index=e2,
                                       peak_index=apex_idx))
        i = max(j, end + 1)

    if single_swing and windows:
        # keep the largest-amplitude excursion (deepest apex = smallest y).
        best = min(windows, key=lambda w: sig[w.peak_index])
        windows = [best]
    return windows
```

> **Why the dwell never splits:** the boundary test requires the hands to be *inside the address band* for `MIN_RETURN_FRAMES` consecutive frames. A mid-swing freeze parks the hands near the apex (or mid-descent) — far outside the band — so `at_address` is `False` there and the inner sustained-return loop is never entered. The excursion simply extends across the freeze. Impact (a brief pass *through* address height on the downswing) is also safe: it is a short touch of the band, far shorter than `MIN_RETURN_FRAMES`, so it is absorbed, not treated as a boundary.

- [ ] **Step 4: Run to verify it passes**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_swing_detect.py -v
```
Expected: **all pass** (single arc=1, three arcs=3, mid-swing dwell=1, fidget rejected, pure-fidget=0, single-swing flag, trajectory builder + interpolation + all-missing). If `test_mid_swing_dwell_stays_one_window` fails, the boundary condition is firing on a non-sustained address touch — verify `MIN_RETURN_FRAMES` is being compared against *consecutive* in-band frames.

- [ ] **Step 5: Commit**

```bash
git add vision/swing_detect.py vision/tests/test_swing_detect.py
git commit -m "feat(vision): hand-trajectory excursion/return swing detector (pause-robust)"
```

---

## Task 3: pipeline.py — feed the trajectory signal into the detector

The pipeline currently builds a motion-energy signal. Swap it for the hand trajectory. Two lines change; `segment.py`, `persist.py`, and the `SwingResult` shape are untouched.

**Files:**
- Modify: `vision/pipeline.py`

- [ ] **Step 1: Edit the import**

In `vision/pipeline.py`, change:
```python
from vision.swing_detect import motion_energy_from_timeline, detect_swings
```
to:
```python
from vision.swing_detect import hand_trajectory_from_timeline, detect_swings
```

- [ ] **Step 2: Edit the signal construction inside `process_video`**

Change:
```python
        energy = motion_energy_from_timeline(face_on)
        windows = detect_swings(energy, single_swing=single_swing)
```
to:
```python
        signal = hand_trajectory_from_timeline(face_on)
        windows = detect_swings(signal, single_swing=single_swing)
```

> No other change. `detect_swings` keeps the same signature and return type, and `segment_swing(down_line, face_on, window)` reads only `window.start_index`/`window.end_index` (it recomputes the apex/top itself), so the new `peak_index` semantics are invisible to it.

- [ ] **Step 3: Quick smoke that the import wiring is intact (no video needed)**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pipeline.py::test_build_timelines_runs_pose_once_per_frame -v
```
Expected: **1 passed** (this test stubs pose and does not call the detector, but it imports `vision.pipeline`, proving the module still imports cleanly after the edit).

- [ ] **Step 4: Commit**

```bash
git add vision/pipeline.py
git commit -m "feat(vision): pipeline feeds hand-trajectory signal to detector"
```

---

## Task 4: Replace the real-video regression — lock golf swing.MOV to exactly 1 swing

This retires the old `test_golf_swing_mov_detects_expected_count` that locked the over-split count of **4** and replaces it with the corrected invariant: the single physical swing in `golf swing.MOV` must resolve to **exactly 1** window. Also confirms the pipeline-level smoke (one swing stored with its 8 moments) still holds.

**Files:**
- Modify: `vision/tests/test_pipeline.py`

- [ ] **Step 1: Remove the stale over-split regression**

In `vision/tests/test_pipeline.py`, **delete the entire** `test_golf_swing_mov_detects_expected_count` function (the one whose docstring records the observed FOUR windows `[208,241] [329,369] [378,422] [435,471]` and asserts `len(results) == 4`). It encoded the bug; it must go.

- [ ] **Step 2: Add the corrected single-swing regression**

Append to `vision/tests/test_pipeline.py`:
```python
@requires_video
def test_golf_swing_mov_resolves_to_one_swing(db):
    """Regression lock for the trajectory detector on golf swing.MOV.

    golf swing.MOV is ONE physical swing recorded on a laggy PC, so it contains
    a genuine top-of-backswing pause AND random lag-artifact freezes. The OLD
    motion-energy detector split it into FOUR windows
    ([208,241] [329,369] [378,422] [435,471]); the hand-trajectory detector
    declares a boundary only on a SUSTAINED return to address, so every
    mid-swing pause is absorbed and the clip resolves to EXACTLY ONE swing.

    HUMAN-EYEBALL NOTE: this count is the algorithm's design target (one swing in
    the clip). If a human review of the annotated clip ever shows a different
    true count, update the asserted number and record why in the commit.
    """
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    results = process_video(db, TEST_VIDEO, player_id=pid, session_id=sid,
                            render=False)
    assert len(results) == 1
    start, end = results[0].frame_range
    assert end - start >= C.MIN_SWING_FRAMES   # a plausibly long swing
```

> The `default` detector now yields one window with no flags, so the old
> `--single-swing` half of the retired test is no longer needed to collapse the
> count. `single_swing=True` is still exercised by the unit suite (Task 2).

- [ ] **Step 3: Confirm the existing pipeline smoke still asserts one swing + 8 moments**

The existing `test_process_video_smoke_stores_swing` already asserts `>= 1`
swing stored with both-view pose frames and `len(get_moments(...)) == 8`. Leave
it as-is; with the trajectory detector it now yields exactly one swing, which
still satisfies `>= 1`. (Optionally tighten its first assertion from
`>= 1` to `== 1` in the same edit if you want the smoke test to lock the count
too — both are correct; keep `>= 1` if you prefer the smoke test to stay loose.)

- [ ] **Step 4: Run the video-dependent pipeline tests (real pose, ~30-60 s on CPU)**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest vision/tests/test_pipeline.py -v
```
Expected: **pass** (or skipped if `golf swing.MOV` is absent). If
`test_golf_swing_mov_resolves_to_one_swing` reports a count other than 1, do
**not** edit the assertion blindly — first print the detected windows
(`process_video` already logs `detected N swing(s)` and each window's frame
range) and eyeball them against the clip per Task 5 before retuning
`ADDRESS_REGION_RADIUS_FRAC` / `MIN_RETURN_FRAMES` / `MIN_SWING_AMPLITUDE_FRAC`
in `constants.py`. This is the intended human-in-the-loop calibration point.

- [ ] **Step 5: Commit**

```bash
git add vision/tests/test_pipeline.py
git commit -m "test(vision): lock golf swing.MOV to exactly 1 swing (trajectory detector)"
```

---

## Task 5: Full-suite green + manual real-video eyeball

**Files:** none modified (verification + human calibration gate).

- [ ] **Step 1: Run the whole vision suite + store suite**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ vision/ -q
```
Expected: fully green. Video-dependent tests pass with `golf swing.MOV` present, else skipped — never failed. Confirm no module still references the removed `motion_energy_from_timeline`, `MOTION_SMOOTH_WINDOW`, `SWING_ENERGY_THRESH_FRAC`, `MIN_STILL_FRAMES`, or `MIN_PEAK_FRAC`:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ vision/ -q
```
(If any import of the old names lingers, the collection step fails — fix the stray reference before proceeding.)

- [ ] **Step 2: Real end-to-end run with an annotated clip (the eyeball gate)**

Run:
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m vision.run --video "golf swing.MOV" --player Chris --render
```
Expected console: `[vision] detected 1 swing(s) in golf swing.MOV`, one
`stored swing id=...` line, and a final `done: 1 swing(s) stored` line. Note we
**drop `--single-swing`** — the whole point of the fix is that the *default*
detector now yields one window on this clip without forcing it.

Open the written `swings/<stamp>_swing0/annotated.mp4` and verify the ONE window
spans the entire physical swing (address through follow-through, *across* the
top pause and any lag freezes) and the 8 phase labels appear in canonical order.
**This is the human validation gate.** If the eyeball shows the window mis-spans
the swing or the true swing count differs, retune the trajectory constants and
update Task 4's assertion to the eyeballed truth, noting why in the commit.

- [ ] **Step 3: (No commit unless a constant was retuned)**

If Step 2 required a constants change, commit it:
```bash
git add vision/constants.py
git commit -m "tune(vision): trajectory thresholds after golf swing.MOV eyeball"
```

---

## Done criteria

- `python -m pytest store/ vision/ -q` is fully green (video-dependent tests pass with `golf swing.MOV` present, else skipped — never failed).
- `vision/swing_detect.py` no longer computes motion energy; it builds a smoothed hand-height trajectory and declares swing boundaries ONLY on a **sustained return to the address rest region** (`MIN_RETURN_FRAMES`), never on motion gaps.
- The critical regression `test_mid_swing_dwell_stays_one_window` passes: a flat dwell in the middle of one arc yields **1** window, proving a mid-swing pause (top-of-backswing OR lag artifact) does not split a swing.
- The synthetic suite proves: single clean arc → 1, three arcs separated by sustained returns → 3, fidget/waggle below thresholds → 0, missing-pose gaps interpolated without crashing.
- `golf swing.MOV` resolves to **exactly 1** swing under the *default* (multi-swing) detector — the old over-split count of 4 is retired — and that one swing is stored with both-view pose frames + 8 moments.
- `SwingWindow` (and therefore `segment.py`, `persist.py`, `pipeline.py`'s `SwingResult` contract) is unchanged; the rewrite is drop-in. All tunables live in `vision/constants.py`.
- The real-video swing count was eyeballed once against the annotated clip (Task 5, Step 2) — the documented human-in-the-loop calibration gate.
```
