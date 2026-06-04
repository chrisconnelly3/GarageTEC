"""Un-foreshortened 3D shoulder/hip side-bend (tilt from horizontal) at top +
impact. Same names as the 2D tilt metrics; method='triangulated_3d'. No-ops when
pose_3d is absent. Address tilt stays 2D (it is already square-accurate)."""
from typing import List, Optional

import numpy as np

from store.models import Metric
from metrics import geometry3d as g3
from metrics.registry import MetricDef, register

UP = np.array([0.0, 1.0, 0.0])
METHOD = "triangulated_3d;confidence=medium"
CONTEXTS = ("top", "impact")


def _vec(pose, a_name, b_name) -> Optional[np.ndarray]:
    by = {l.name: l for l in pose}
    a, b = by.get(a_name), by.get(b_name)
    if a is None or b is None:
        return None
    return np.array([b.x - a.x, b.y - a.y, b.z - a.z])


def _tilt(ctx, name, a_name, b_name) -> List[Metric]:
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_3d_at(kind)
        if pose is None:
            continue
        v = _vec(pose, a_name, b_name)
        if v is None:
            continue
        deg = g3.tilt_from_horizontal(v, UP)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=deg, unit="deg", method=METHOD))
    return out


def shoulder_tilt_3d(ctx) -> List[Metric]:
    return _tilt(ctx, "shoulder_tilt_deg", "left_shoulder", "right_shoulder")


def hip_tilt_3d(ctx) -> List[Metric]:
    return _tilt(ctx, "hip_tilt_deg", "left_hip", "right_hip")


register(MetricDef(name="shoulder_tilt_deg", view="threed",
                   contexts=CONTEXTS, fn=shoulder_tilt_3d))
register(MetricDef(name="hip_tilt_deg", view="threed",
                   contexts=CONTEXTS, fn=hip_tilt_3d))
