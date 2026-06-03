"""Early extension: hip-center forward (+x toward ball) and vertical (up) shift
from address, down-line, magnitude in inches via ppi. Reported at impact (vs
address) and max (peak magnitude over the swing).
"""
import math
from typing import List, Optional

from store.models import Landmark, Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

METHOD = "shoulder_ratio_0.24"


def _hip_center(pose) -> Optional[tuple]:
    lh = g.pick(pose, "left_hip")
    rh = g.pick(pose, "right_hip")
    if lh is None or rh is None:
        return None
    return g.midpoint(lh, rh)


def _magnitude_in(ref, cur, ppi) -> float:
    fwd, vert = g.forward_vertical_displacement(ref, cur)
    return math.hypot(fwd, vert) / ppi


def early_extension(ctx) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    addr = ctx.pose_at("down_line", "address")
    if addr is None:
        return []
    ref = _hip_center(addr)
    if ref is None:
        return []

    out: List[Metric] = []
    imp = ctx.pose_at("down_line", "impact")
    if imp is not None:
        cur = _hip_center(imp)
        if cur is not None:
            out.append(Metric(swing_id=ctx.swing_id, name="early_extension_in",
                              context="impact", value=_magnitude_in(ref, cur, ctx.ppi),
                              unit="in", method=METHOD))

    max_mag = 0.0
    for _idx, pose in sorted(ctx.frames("down_line").items()):
        cur = _hip_center(pose)
        if cur is None:
            continue
        mag = _magnitude_in(ref, cur, ctx.ppi)
        if mag > max_mag:
            max_mag = mag
    if max_mag > 0.0:
        out.append(Metric(swing_id=ctx.swing_id, name="early_extension_in",
                          context="max", value=max_mag, unit="in", method=METHOD))
    return out


register(MetricDef(name="early_extension_in", view="down_line",
                   contexts=("impact", "max"), fn=early_extension))
