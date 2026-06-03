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
