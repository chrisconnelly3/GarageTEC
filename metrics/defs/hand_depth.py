"""Hand depth: horizontal distance of the hands (mid-wrist) from the trail
shoulder, down-line, in inches via ppi. Reported at top and impact. The trail
shoulder is the right shoulder for a right-handed player, left for a lefty.
"""
from typing import List, Optional

from store.models import Metric
from metrics import geometry as g
from metrics.registry import MetricDef, register

CONTEXTS = ("top", "impact")
METHOD = "shoulder_ratio_0.24"


def _mid_wrist_x(pose) -> Optional[float]:
    lw = g.pick(pose, "left_wrist")
    rw = g.pick(pose, "right_wrist")
    if lw is None or rw is None:
        return None
    return (lw.x + rw.x) / 2.0


def _trail_shoulder_name(handedness) -> str:
    return "left_shoulder" if (handedness or "R").upper() == "L" else "right_shoulder"


def hand_depth(ctx) -> List[Metric]:
    if ctx.ppi <= 0.0:
        return []
    trail = _trail_shoulder_name(ctx.player.handedness)
    out: List[Metric] = []
    for kind in CONTEXTS:
        pose = ctx.pose_at("down_line", kind)
        if pose is None:
            continue
        shoulder = g.pick(pose, trail)
        wrist_x = _mid_wrist_x(pose)
        if shoulder is None or wrist_x is None:
            continue
        depth_px = abs(wrist_x - shoulder.x)
        out.append(Metric(swing_id=ctx.swing_id, name="hand_depth_in",
                          context=kind, value=depth_px / ctx.ppi, unit="in",
                          method=METHOD))
    return out


register(MetricDef(name="hand_depth_in", view="down_line",
                   contexts=CONTEXTS, fn=hand_depth))
