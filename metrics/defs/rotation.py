"""Rough 2D shoulder turn and hip turn from width foreshortening vs address,
face-on, at top and impact. COARSE estimates: every row is tagged
method="foreshortening_2d;confidence=low".
"""
from typing import List, Optional

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("top", "impact")
METHOD = "foreshortening_2d;confidence=low"


def _width(pose, left_name, right_name) -> Optional[float]:
    left = g.pick(pose, left_name)
    right = g.pick(pose, right_name)
    if left is None or right is None:
        return None
    return abs(right.x - left.x)


def _turn(ctx, name, left_name, right_name) -> List[Metric]:
    addr = ctx.pose_at("face_on", "address")
    if addr is None:
        return []
    addr_w = _width(addr, left_name, right_name)
    if addr_w is None or addr_w <= 0.0:
        return []
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        cur_w = _width(pose, left_name, right_name)
        if cur_w is None:
            continue
        deg = g.foreshortening_to_rotation_deg(cur_w, addr_w)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_turn(ctx) -> List[Metric]:
    return _turn(ctx, "shoulder_turn_deg", "left_shoulder", "right_shoulder")


def hip_turn(ctx) -> List[Metric]:
    return _turn(ctx, "hip_turn_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_turn_deg", view="face_on",
                   contexts=CONTEXTS, fn=shoulder_turn))
register(MetricDef(name="hip_turn_deg", view="face_on",
                   contexts=CONTEXTS, fn=hip_turn))
