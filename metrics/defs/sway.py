"""Head sway and hip sway: lateral displacement of a body center from its
ADDRESS position, in inches via the shoulder-ratio ppi ruler. Reported at top,
impact, and max (peak |displacement| over the swing). Positive = toward target;
target side inferred from net hip motion address->impact.
"""
from typing import Callable, List, Optional

from store.models import Landmark, Metric
from metrics import geometry as g

from metrics.registry import MetricDef, register

REPORT_CONTEXTS = ("top", "impact")
METHOD = "shoulder_ratio_0.24"


def _center(pose: List[Landmark], kind: str) -> Optional[tuple]:
    if kind == "head":
        n = g.pick(pose, "nose")
        return (n.x, n.y) if n is not None else None
    lh = g.pick(pose, "left_hip")
    rh = g.pick(pose, "right_hip")
    if lh is None or rh is None:
        return None
    return g.midpoint(lh, rh)


def _sway(ctx, name: str, body: str) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    addr_pose = ctx.pose_at("face_on", "address")
    if addr_pose is None:
        return []
    ref = _center(addr_pose, body)
    if ref is None:
        return []

    # Direction sign: net x-motion of hip center address->impact; default +1.
    sign = _target_sign(ctx, ref if body == "hip" else None)

    out: List[Metric] = []
    for kind in REPORT_CONTEXTS:
        pose = ctx.pose_at("face_on", kind)
        if pose is None:
            continue
        cur = _center(pose, body)
        if cur is None:
            continue
        dx_px = g.lateral_displacement(ref, cur)
        out.append(Metric(swing_id=ctx.swing_id, name=name, context=kind,
                          value=sign * dx_px / ctx.ppi, unit="in", method=METHOD))

    # max: scan every frame, pick the largest |dx|.
    max_px = 0.0
    for _idx, pose in sorted(ctx.frames("face_on").items()):
        cur = _center(pose, body)
        if cur is None:
            continue
        dx_px = g.lateral_displacement(ref, cur)
        if abs(dx_px) > abs(max_px):
            max_px = dx_px
    if max_px != 0.0:
        out.append(Metric(swing_id=ctx.swing_id, name=name, context="max",
                          value=sign * max_px / ctx.ppi, unit="in", method=METHOD))
    return out


def _target_sign(ctx, hip_ref) -> float:
    """+1 if net hip-center x increases address->impact, else -1. Falls back to
    +1 when impact or hips are missing."""
    addr = ctx.pose_at("face_on", "address")
    imp = ctx.pose_at("face_on", "impact")
    if addr is None or imp is None:
        return 1.0
    a = _center(addr, "hip")
    b = _center(imp, "hip")
    if a is None or b is None:
        return 1.0
    return 1.0 if (b[0] - a[0]) >= 0 else -1.0


def hip_sway(ctx) -> List[Metric]:
    return _sway(ctx, "hip_sway_in", "hip")


def head_sway(ctx) -> List[Metric]:
    return _sway(ctx, "head_sway_in", "head")


register(MetricDef(name="hip_sway_in", view="face_on",
                   contexts=("top", "impact", "max"), fn=hip_sway))
register(MetricDef(name="head_sway_in", view="face_on",
                   contexts=("top", "impact", "max"), fn=head_sway))
