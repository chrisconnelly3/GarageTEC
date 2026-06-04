"""True 3D shoulder/hip turn + X-factor from triangulated pose, relative to
address, about world up (+Y). No-ops when pose_3d is absent so the 2D registry
is unaffected. Same metric names as the 2D versions; method='triangulated_3d'.
"""
from typing import List, Optional

import numpy as np

from store.models import Metric
from metrics import geometry3d as g3
from metrics.registry import MetricDef, register

UP = np.array([0.0, 1.0, 0.0])
METHOD = "triangulated_3d;confidence=medium"
REPORT = ("top", "impact")


def _vec(pose, a_name, b_name) -> Optional[np.ndarray]:
    by = {l.name: l for l in pose}
    a, b = by.get(a_name), by.get(b_name)
    if a is None or b is None:
        return None
    return np.array([b.x - a.x, b.y - a.y, b.z - a.z])


def _turn(ctx, name, a_name, b_name) -> List[Metric]:
    addr = ctx.pose_3d_at("address")
    if addr is None:
        return []
    v0 = _vec(addr, a_name, b_name)
    if v0 is None:
        return []
    out: List[Metric] = []
    for kind in REPORT:
        pose = ctx.pose_3d_at(kind)
        if pose is None:
            continue
        v = _vec(pose, a_name, b_name)
        if v is None:
            continue
        deg = g3.turn_about_axis(v0, v, UP)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_turn(ctx) -> List[Metric]:
    return _turn(ctx, "shoulder_turn_deg", "left_shoulder", "right_shoulder")


def hip_turn(ctx) -> List[Metric]:
    return _turn(ctx, "hip_turn_deg", "left_hip", "right_hip")


def _turn_value(ctx, a_name, b_name, kind) -> Optional[float]:
    addr = ctx.pose_3d_at("address")
    pose = ctx.pose_3d_at(kind)
    if addr is None or pose is None:
        return None
    v0, v = _vec(addr, a_name, b_name), _vec(pose, a_name, b_name)
    if v0 is None or v is None:
        return None
    return g3.turn_about_axis(v0, v, UP)


def x_factor(ctx) -> List[Metric]:
    sh = _turn_value(ctx, "left_shoulder", "right_shoulder", "top")
    hp = _turn_value(ctx, "left_hip", "right_hip", "top")
    if sh is None or hp is None:
        return []
    return [Metric(swing_id=ctx.swing_id, name="x_factor_deg", context="top",
                  value=sh - hp, unit="deg", method=METHOD)]


def x_factor_stretch(ctx) -> List[Metric]:
    """Peak X-factor over top->impact frames minus X-factor at top. Needs the
    full 3D timeline between the top and impact moment frames."""
    top = ctx.frame_index_for("face_on", "top") or ctx.frame_index_for("down_line", "top")
    imp = ctx.frame_index_for("face_on", "impact") or ctx.frame_index_for("down_line", "impact")
    addr = ctx.pose_3d_at("address")
    if top is None or imp is None or addr is None or not ctx.pose_3d:
        return []
    v0s = _vec(addr, "left_shoulder", "right_shoulder")
    v0h = _vec(addr, "left_hip", "right_hip")
    if v0s is None or v0h is None:
        return []
    xf_top = None
    peak = None
    lo, hi = min(top, imp), max(top, imp)
    for idx in range(lo, hi + 1):
        pose = ctx.pose_3d.get(idx)
        if not pose:
            continue
        vs = _vec(pose, "left_shoulder", "right_shoulder")
        vh = _vec(pose, "left_hip", "right_hip")
        if vs is None or vh is None:
            continue
        xf = g3.turn_about_axis(v0s, vs, UP) - g3.turn_about_axis(v0h, vh, UP)
        if idx == top:
            xf_top = xf
        peak = xf if peak is None or abs(xf) > abs(peak) else peak
    if xf_top is None or peak is None:
        return []
    return [Metric(swing_id=ctx.swing_id, name="x_factor_stretch_deg",
                  context="downswing", value=abs(peak) - abs(xf_top),
                  unit="deg", method=METHOD)]


register(MetricDef(name="shoulder_turn_deg", view="threed",
                   contexts=REPORT, fn=shoulder_turn))
register(MetricDef(name="hip_turn_deg", view="threed",
                   contexts=REPORT, fn=hip_turn))
register(MetricDef(name="x_factor_deg", view="threed",
                   contexts=("top",), fn=x_factor))
register(MetricDef(name="x_factor_stretch_deg", view="threed",
                   contexts=("downswing",), fn=x_factor_stretch))
