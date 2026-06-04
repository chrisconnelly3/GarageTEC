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
