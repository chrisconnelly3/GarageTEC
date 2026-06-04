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
