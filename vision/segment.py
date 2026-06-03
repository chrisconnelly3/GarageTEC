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
