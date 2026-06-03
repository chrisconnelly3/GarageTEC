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
