"""Compute OUR metrics for one GolfDB swing from its source video.

Given a manifest entry (manifest.py) and a downloaded source video, this:
  1. crops the bbox region at NATIVE resolution,
  2. runs OUR vision.pose at the shipped address/top/impact event frames,
  3. computes metrics using the SAME geometry primitives as the production
     metric defs (metrics.geometry), so the pro reference is in our exact
     metric definitions:
       - shoulder_tilt_deg / hip_tilt_deg  (face_on, vs horizontal)  -- EXACT
       - spine_angle_deg                   (down_line, vs vertical)  -- EXACT
       - hip_sway / head_sway              (face_on, % shoulder width) -- SCALE-FREE
     Rotation (foreshortening) and DTL positional metrics are intentionally not
     computed (junk / no stable scale-free reference yet).

Returns a per-swing record: {id, player, view, club, slow, metrics:{...}, vis}
where metrics maps "<name>@<phase>" -> float, and `vis` is the mean landmark
visibility at the keyframes (a pose-quality gate the aggregator can threshold).
"""
from typing import Dict, List, Optional

import cv2

from store.models import Landmark
from vision.pose import PoseEstimator
from metrics import geometry as g
from coach.norms.pro_reference.manifest import phase_frame

PHASES = ("address", "top", "impact")

# Landmarks whose mean visibility gates a usable keyframe pose.
_VIS_KEYS = ("left_shoulder", "right_shoulder", "left_hip", "right_hip")


def _crop_box(width: int, height: int, bbox) -> tuple:
    x = int(width * bbox[0]); y = int(height * bbox[1])
    w = int(width * bbox[2]); h = int(height * bbox[3])
    # clamp to frame
    x = max(0, x); y = max(0, y)
    w = min(w, width - x); h = min(h, height - y)
    return x, y, w, h


def _by_name(lms: List[Landmark]) -> Dict[str, Landmark]:
    return {l.name: l for l in lms}


def _mean_vis(lms: List[Landmark]) -> float:
    bn = _by_name(lms)
    vals = [bn[k].visibility for k in _VIS_KEYS if k in bn]
    return sum(vals) / len(vals) if vals else 0.0


def _shoulder_width_px(lms: List[Landmark]) -> Optional[float]:
    bn = _by_name(lms)
    ls, rs = bn.get("left_shoulder"), bn.get("right_shoulder")
    if ls is None or rs is None:
        return None
    w = abs(rs.x - ls.x)
    return w if w > 1e-6 else None


# GolfDB view labels are imperfect (~15% of clips are mislabeled). We trust the
# pose GEOMETRY instead: face-on shows full biacromial (shoulder) breadth, so
# shoulder_width / torso_height is LARGE (~0.5-0.95); down-the-line foreshortens
# the shoulders, so it is SMALL (~0.02-0.15). Calibrated on labeled clips: the
# two populations are cleanly separated by a gap from ~0.15 to ~0.5.
VIEW_RATIO_THRESHOLD = 0.33


def detect_view(address_pose: Optional[List[Landmark]]) -> Optional[str]:
    """Classify the camera view from the address pose geometry, or None if it
    can't be determined. Overrides GolfDB's (imperfect) view label."""
    if address_pose is None:
        return None
    sw = _shoulder_width_px(address_pose)
    if sw is None:
        return None
    bn = _by_name(address_pose)
    ls, rs = bn.get("left_shoulder"), bn.get("right_shoulder")
    lh, rh = bn.get("left_hip"), bn.get("right_hip")
    if not (ls and rs and lh and rh):
        return None
    sc_y = (ls.y + rs.y) / 2.0
    hc_y = (lh.y + rh.y) / 2.0
    torso_h = abs(sc_y - hc_y)
    if torso_h <= 1e-6:
        return None
    return "face_on" if (sw / torso_h) >= VIEW_RATIO_THRESHOLD else "down_line"


_SEEK_BACKOFF = 20   # decode this many frames before a target to land exact


def _read_exact(cap, target: int):
    """Return the decoded frame at exactly `target`, seeking to a nearby prior
    keyframe and decoding forward (cv2 POS_FRAMES seeks to the nearest prior
    keyframe, so we re-read until the reported position reaches target)."""
    seek_to = max(0, target - _SEEK_BACKOFF)
    cap.set(cv2.CAP_PROP_POS_FRAMES, seek_to)
    frame = None
    while True:
        pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        ok, img = cap.read()
        if not ok:
            return None
        if pos >= target:        # `pos` is the index of the frame just read
            return img
        frame = img
    return frame


def extract_poses(video_path: str, bbox, events) -> Dict[str, Optional[List[Landmark]]]:
    """Run pose at the three keyframes; return {phase: landmarks|None}.

    Seeks to each keyframe (decoding forward from a nearby keyframe for exact
    landing) rather than decoding the whole clip -- the keyframes can sit ~1000
    frames into a slow-mo clip, so this is the bulk of the speedup.
    """
    targets = {p: phase_frame(events, p) for p in PHASES}
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {p: None for p in PHASES}
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    x, y, w, h = _crop_box(W, H, bbox)
    pose = PoseEstimator(view="face_on")  # view label irrelevant to estimate()
    out: Dict[str, Optional[List[Landmark]]] = {p: None for p in PHASES}
    try:
        for phase in PHASES:
            frame = _read_exact(cap, targets[phase])
            if frame is None:
                continue
            out[phase] = pose.estimate(frame[y:y + h, x:x + w])
    finally:
        pose.close()
        cap.release()
    return out


def _angle_metrics(poses, our_view: str) -> Dict[str, float]:
    """Exact angle metrics, matching the production metric defs exactly."""
    m: Dict[str, float] = {}
    for phase in PHASES:
        lms = poses.get(phase)
        if lms is None:
            continue
        bn = _by_name(lms)
        if our_view == "face_on":
            ls, rs = bn.get("left_shoulder"), bn.get("right_shoulder")
            lh, rh = bn.get("left_hip"), bn.get("right_hip")
            if ls and rs:
                m[f"shoulder_tilt_deg@{phase}"] = g.line_angle_vs_horizontal(ls, rs)
            if lh and rh:
                m[f"hip_tilt_deg@{phase}"] = g.line_angle_vs_horizontal(lh, rh)
        elif our_view == "down_line":
            ls, rs = bn.get("left_shoulder"), bn.get("right_shoulder")
            lh, rh = bn.get("left_hip"), bn.get("right_hip")
            if ls and rs and lh and rh:
                sc = Landmark("sc", (ls.x + rs.x) / 2, (ls.y + rs.y) / 2, 0, 1)
                hc = Landmark("hc", (lh.x + rh.x) / 2, (lh.y + rh.y) / 2, 0, 1)
                m[f"spine_angle_deg@{phase}"] = g.line_angle_vs_vertical(sc, hc)
    return m


def _sway_metrics(poses) -> Dict[str, float]:
    """Face-on hip/head sway as a FRACTION of address shoulder width
    (scale-free; positive = toward target, sign from net hip motion)."""
    addr = poses.get("address")
    if addr is None:
        return {}
    sw = _shoulder_width_px(addr)
    if sw is None:
        return {}
    bn_a = _by_name(addr)

    def center(lms, body):
        bn = _by_name(lms)
        if body == "head":
            n = bn.get("nose")
            return (n.x, n.y) if n else None
        lh, rh = bn.get("left_hip"), bn.get("right_hip")
        return g.midpoint(lh, rh) if (lh and rh) else None

    refs = {b: center(addr, b) for b in ("hip", "head")}
    # direction sign from net hip-center x address->impact
    sign = 1.0
    imp = poses.get("impact")
    if imp is not None and refs["hip"] is not None:
        ci = center(imp, "hip")
        if ci is not None:
            sign = 1.0 if (ci[0] - refs["hip"][0]) >= 0 else -1.0

    m: Dict[str, float] = {}
    for body, name in (("hip", "hip_sway_sw"), ("head", "head_sway_sw")):
        ref = refs[body]
        if ref is None:
            continue
        for phase in ("top", "impact"):
            lms = poses.get(phase)
            if lms is None:
                continue
            cur = center(lms, body)
            if cur is None:
                continue
            m[f"{name}@{phase}"] = sign * (cur[0] - ref[0]) / sw
    return m


def extract_swing(video_path: str, entry: Dict,
                  min_vis: float = 0.5) -> Optional[Dict]:
    """Full per-swing extraction. Returns a record dict, or None if pose at the
    keyframes is too poor (mean keyframe visibility < min_vis) or missing."""
    poses = extract_poses(video_path, entry["bbox"], entry["events"])
    present = [p for p in PHASES if poses.get(p) is not None]
    if not present:
        return None
    vis = sum(_mean_vis(poses[p]) for p in present) / len(present)
    if vis < min_vis:
        return None

    # Trust pose geometry over GolfDB's (imperfect) view label for routing.
    detected = detect_view(poses.get("address")) or entry["our_view"]

    metrics: Dict[str, float] = {}
    metrics.update(_angle_metrics(poses, detected))
    if detected == "face_on":
        metrics.update(_sway_metrics(poses))
    if not metrics:
        return None
    return {
        "id": entry["id"],
        "player": entry["player"],
        "view_label": entry["view"],          # GolfDB's label (provenance)
        "view": "face-on" if detected == "face_on" else "down-the-line",  # detected
        "view_detected_from_pose": detected != entry["our_view"]
                                   and detect_view(poses.get("address")) is not None,
        "club": entry["club"],
        "slow": entry["slow"],
        "vis": round(vis, 3),
        "metrics": {k: round(v, 3) for k, v in metrics.items()},
    }
