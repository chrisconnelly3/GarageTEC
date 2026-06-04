# coach/golftec.py
"""Load the authoritative GolfTEC reference and compare a live metric value to
its tour-pro target, honoring the 2D-vs-3D gate: a (metric, phase) is only
comparable when it is two_d_comparable_now OR a 3D value is available.
"""
import json
import os

_PATH = os.path.join(os.path.dirname(__file__), "norms", "pro_reference",
                     "golftec_reference.json")


def load(path=None):
    with open(path or _PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def compare(name, context, value, has_3d=False, ref=None):
    """Return {comparable, target, delta, reason}. comparable is False (with a
    reason) when the metric/phase needs 3D and none is available, or when the
    metric/phase is unknown."""
    ref = load() if ref is None else ref
    entry = ref.get(name)
    if entry is None or "contexts" not in entry:
        return {"comparable": False, "target": None, "delta": None,
                "reason": "no_golftec_target"}
    ctx = entry["contexts"].get(context)
    if ctx is None:
        return {"comparable": False, "target": None, "delta": None,
                "reason": "no_phase_target"}
    target = ctx["value"]
    if ctx.get("two_d_comparable_now") or has_3d:
        return {"comparable": True, "target": target,
                "delta": value - target, "reason": None}
    return {"comparable": False, "target": target, "delta": None,
            "reason": "needs_3d"}
