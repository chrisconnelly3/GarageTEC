# coach/golftec.py
"""Load the authoritative GolfTEC reference and compare a live metric value to
its tour-pro target, honoring the 2D-vs-3D gate: a (metric, phase) is only
comparable when it is two_d_comparable_now OR a 3D value is available.
"""
import json
import os

_DIR = os.path.join(os.path.dirname(__file__), "norms", "pro_reference")
_PATH = os.path.join(_DIR, "golftec_reference.json")
_SUPP_PATH = os.path.join(_DIR, "supplementary_reference.json")


def load(path=None, supp_path=None):
    """Authoritative GolfTEC references merged with the supplementary (non-GolfTEC,
    source-tagged) references. GolfTEC wins on any key collision."""
    with open(path or _PATH, "r", encoding="utf-8") as f:
        ref = json.load(f)
    sp = supp_path or _SUPP_PATH
    if os.path.exists(sp):
        with open(sp, "r", encoding="utf-8") as f:
            for name, entry in json.load(f).items():
                existing = ref.get(name)
                # Only override if GolfTEC has no real target (no "contexts" key)
                if existing is None or "contexts" not in existing:
                    ref[name] = entry
    return ref


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


# Order phases for a tidy "vs tour pro" panel.
_PHASE_ORDER = {"address": 0, "top": 1, "impact": 2, "finish": 3, "downswing": 4}


def benchmark_metrics(metrics, ref=None):
    """Build the 'vs tour pro' rows for a swing's metrics. `metrics` is a list of
    dicts {name, context, value, unit, method}. Per row, 3D availability comes
    from the row's own method (`triangulated_3d*`), so the 2D/3D gate is honored
    per metric/phase. Only metrics with a GolfTEC target are returned; when both
    a 2D and a 3D row exist for the same (name, context), the comparable one
    wins. Each row: {name, context, value, unit, target, delta, comparable,
    reason}."""
    ref = load() if ref is None else ref
    rows = {}
    for m in metrics:
        name, context, value = m.get("name"), m.get("context"), m.get("value")
        if name is None or context is None or value is None:
            continue
        has_3d = str(m.get("method") or "").startswith("triangulated_3d")
        c = compare(name, context, value, has_3d=has_3d, ref=ref)
        if c["reason"] in ("no_golftec_target", "no_phase_target"):
            continue                              # no tour target to show
        row = {
            "name": name, "context": context, "value": round(value, 1),
            "unit": m.get("unit"), "target": c["target"],
            "delta": round(c["delta"], 1) if c["delta"] is not None else None,
            "comparable": c["comparable"], "reason": c["reason"],
        }
        key = (name, context)
        prev = rows.get(key)
        if prev is None or (row["comparable"] and not prev["comparable"]):
            rows[key] = row
    return sorted(rows.values(),
                  key=lambda r: (r["name"], _PHASE_ORDER.get(r["context"], 9)))
