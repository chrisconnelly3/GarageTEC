"""Shoulder tilt and hip tilt: line angle vs horizontal, face-on, in degrees.
Exact (no calibration). Reported at address, top, impact.
"""
from typing import List

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("address", "top", "impact")


def _line_tilt(ctx, name, left_name, right_name) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        left = g.pick(pose, left_name)
        right = g.pick(pose, right_name)
        if left is None or right is None:
            continue
        angle = g.line_angle_vs_horizontal(left, right)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=angle, unit="deg", method="exact"))
    return out


def shoulder_tilt(ctx) -> List[Metric]:
    return _line_tilt(ctx, "shoulder_tilt_deg", "left_shoulder", "right_shoulder")


def hip_tilt(ctx) -> List[Metric]:
    return _line_tilt(ctx, "hip_tilt_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_tilt_deg", view="face_on",
                   contexts=CONTEXTS, fn=shoulder_tilt))
register(MetricDef(name="hip_tilt_deg", view="face_on",
                   contexts=CONTEXTS, fn=hip_tilt))
