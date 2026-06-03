"""Spine angle: torso (hip-center -> shoulder-center) lean from vertical,
down-line view, in degrees. Exact. Reported at address, top, impact.
"""
from typing import List

from store.models import Landmark, Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("address", "top", "impact")


def _center_landmark(pose, a_name, b_name, out_name):
    a = g.pick(pose, a_name)
    b = g.pick(pose, b_name)
    if a is None or b is None:
        return None
    cx, cy = g.midpoint(a, b)
    return Landmark(name=out_name, x=cx, y=cy, z=0.0, visibility=1.0)


def spine_angle(ctx) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("down_line", kind)
        if pose is None:
            continue
        shoulder = _center_landmark(pose, "left_shoulder", "right_shoulder", "sh_c")
        hip = _center_landmark(pose, "left_hip", "right_hip", "hip_c")
        if shoulder is None or hip is None:
            continue
        angle = g.line_angle_vs_vertical(shoulder, hip)
        out.append(Metric(swing_id=ctx.swing_id, name="spine_angle_deg",
                          context=kind, value=angle, unit="deg", method="exact"))
    return out


register(MetricDef(name="spine_angle_deg", view="down_line",
                   contexts=CONTEXTS, fn=spine_angle))
