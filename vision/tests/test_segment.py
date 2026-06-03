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
