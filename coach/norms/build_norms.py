"""Generate coach/norms/norms.json from the vendored CaddieSet CSV.

HONEST norms: only metrics whose geometric definition genuinely matches a
CaddieSet feature get a real band (mixed-skill population p10-p90, NOT a
validated ideal). Everything else is confidence:"none" -> the coach falls back
to the player's own history. See coach/norms/data/SOURCE.md for attribution and
the plan doc for the full mapping rationale.

Stdlib only (csv, json, math) — no pandas/numpy.
"""
import csv
import datetime
import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = os.path.join(DATA_DIR, "CaddieSet.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "norms.json")

CLAMP_ARTIFACTS = (0.0, 180.0)


def _percentile(sorted_vals, p):
    """Linear-interpolation percentile, p in [0,1]. sorted_vals must be sorted
    and non-empty."""
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(math.floor(k))
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


WINSORIZE_MIN_N = 100


def clean_values(raw, drop_clamps=CLAMP_ARTIFACTS):
    """Drop None/inf/nan, drop exact clamp artifacts, then winsorize the
    survivors to their [p1, p99] (clip tails inward; preserve count).

    Winsorizing is only applied once there are enough surviving values
    (>= WINSORIZE_MIN_N) for the 1st/99th percentiles to be meaningful. On
    tiny lists p1/p99 interpolate between the only few points and would move
    legitimate values, so we leave small samples untouched. The real CaddieSet
    columns all have hundreds of rows, so this never disables winsorizing in
    production."""
    vals = []
    for v in raw:
        if v is None:
            continue
        f = float(v)
        if math.isinf(f) or math.isnan(f):
            continue
        if any(f == c for c in drop_clamps):
            continue
        vals.append(f)
    if len(vals) < WINSORIZE_MIN_N:
        return vals
    s = sorted(vals)
    lo = _percentile(s, 0.01)
    hi = _percentile(s, 0.99)
    return [min(max(v, lo), hi) for v in vals]


def percentiles(clean_vals):
    """Return (p10, median, p90) rounded to 2 dp, or None if empty."""
    if not clean_vals:
        return None
    s = sorted(clean_vals)
    return (round(_percentile(s, 0.10), 2),
            round(_percentile(s, 0.50), 2),
            round(_percentile(s, 0.90), 2))


def convert(value, kind):
    """Axis/unit conversion for one value.
    'none'                     -> identity (same axis & units).
    'vertical_from_horizontal' -> 90 - value (CaddieSet vs horizontal -> ours
                                  vs vertical).
    """
    if kind == "none":
        return value
    if kind == "vertical_from_horizontal":
        return 90.0 - value
    raise ValueError(f"unknown conversion kind: {kind!r}")


# --- The mapping (single source of truth; see plan doc for rationale) ---------

# Named swing phase -> CaddieSet event index (0=address ... 7=finish).
# ASSUMPTION: standard 8-event sequence; CaddieSet README does not name events.
EVENT = {"address": 0, "top": 3, "impact": 5}

SOURCE_LINE = (
    "CaddieSet (damilab, MIT) - mixed-skill population p10-p90 typical range, "
    "NOT a validated ideal. https://github.com/damilab/CaddieSet"
)

# (our_metric, context) -> (caddieset_feature, view, conversion_kind)
MAPPING = {
    ("shoulder_tilt_deg", "address"): ("SHOULDER-ANGLE", "FACEON", "none"),
    ("shoulder_tilt_deg", "top"):     ("SHOULDER-ANGLE", "FACEON", "none"),
    ("shoulder_tilt_deg", "impact"):  ("SHOULDER-ANGLE", "FACEON", "none"),
    ("spine_angle_deg", "address"):   ("SPINE-ANGLE", "DTL", "vertical_from_horizontal"),
    ("spine_angle_deg", "impact"):    ("SPINE-ANGLE", "DTL", "vertical_from_horizontal"),
    # NOTE: spine top (event 3) intentionally absent — CaddieSet has no 3-SPINE-ANGLE.
}

MAPPED_UNITS = {"shoulder_tilt_deg": "deg", "spine_angle_deg": "deg"}

# Metrics with NO defensible CaddieSet source -> confidence:"none".
NONE_REASONS = {
    "hip_tilt_deg":
        "CaddieSet has no hip-line-angle-vs-horizontal feature; HIP-LINE/"
        "HIP-SHIFTED are displacements and HIP-ROTATION/HIP-ANGLE are rotations.",
    "shoulder_turn_deg":
        "CaddieSet SHOULDER-ANGLE is a tilt vs horizontal, not "
        "rotation-relative-to-address; no shoulder-turn feature exists.",
    "hip_turn_deg":
        "Closest CaddieSet features (HIP-ROTATION/HIP-ANGLE, pelvis rotation "
        "vs address) have severe clamp artifacts (floods of 0.0, spikes of "
        "180.0), an unverifiable zero-point/axis vs our coarse foreshortening "
        "estimate, and are absent at impact (FACEON) — not defensible.",
    "hip_sway_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "head_sway_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "early_extension_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "hand_depth_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
}

ALL_METRICS = sorted(MAPPED_UNITS.keys() | NONE_REASONS.keys())


def _load_rows(csv_path):
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _column_values(rows, view, column):
    """Float-parse one column for rows of the given View. Blank -> skipped,
    'inf'/'nan' strings -> kept as float so clean_values drops them."""
    out = []
    for r in rows:
        if r.get("View") != view:
            continue
        raw = r.get(column, "")
        if raw is None or raw == "":
            continue
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def _band_for(rows, our_metric, context):
    feature, view, conv = MAPPING[(our_metric, context)]
    column = f"{EVENT[context]}-{feature}"
    raw = _column_values(rows, view, column)
    cleaned = clean_values(raw)
    if conv != "none":
        cleaned = [convert(v, conv) for v in cleaned]
    pct = percentiles(cleaned)
    if pct is None:
        return None
    p10, med, p90 = pct
    low, high = min(p10, p90), max(p10, p90)   # ascending even after 90-x flip
    return {"range": [low, high], "median": med, "n": len(cleaned)}


def build_entries(csv_path=CSV_PATH):
    """Return {metric_name: entry} for all 9 metrics, schema-compatible with
    coach.norms (each entry has range/units/source/confidence)."""
    rows = _load_rows(csv_path)
    entries = {}

    # Mapped metrics: collect per-context bands; the top-level `range` is the
    # union (min low .. max high) across that metric's contexts so the simple
    # compare() path still works; per-context detail lives under `contexts`.
    mapped_metrics = sorted({m for (m, _c) in MAPPING})
    for m in mapped_metrics:
        contexts = {}
        for (mm, ctx) in MAPPING:
            if mm != m:
                continue
            band = _band_for(rows, m, ctx)
            if band is not None:
                contexts[ctx] = band
        lows = [c["range"][0] for c in contexts.values()]
        highs = [c["range"][1] for c in contexts.values()]
        entries[m] = {
            "range": [min(lows), max(highs)] if contexts else [],
            "units": MAPPED_UNITS[m],
            "source": SOURCE_LINE,
            "confidence": "medium",
            "contexts": contexts,
            "comment": ("Mixed-skill population typical range (p10-p90), NOT a "
                        "validated ideal. Per-phase bands under 'contexts'."),
        }

    for m, reason in NONE_REASONS.items():
        entries[m] = {
            "range": [],
            "units": "in" if m.endswith("_in") else "deg",
            "source": None,
            "confidence": "none",
            "reason": reason,
            "comment": "No defensible CaddieSet source; coach uses player history.",
        }

    return entries


def build_meta():
    return {
        "status": "Generated from CaddieSet, not human-curated ideals",
        "generated": datetime.date.today().isoformat(),
        "note": (
            "Bands are CaddieSet mixed-skill POPULATION typical ranges "
            "(p10-p90), NOT validated ideal/good-bad thresholds and NOT a "
            "human-curated standard. Treat them as 'where most swings land', "
            "not 'what you should do'. Metrics with confidence 'none' have no "
            "defensible CaddieSet source and the coach falls back to the "
            "player's own history for them."
        ),
        "attribution": (
            "Derived from CaddieSet (damilab, MIT License). "
            "https://github.com/damilab/CaddieSet — see coach/norms/data/SOURCE.md."
        ),
        "event_phase_assumption": (
            "CaddieSet events 0..7 mapped to phases address=0, top=3, impact=5 "
            "(standard 8-event golf sequence; upstream does not name events)."
        ),
        "units_doc": "range is [low, high] inclusive in the stated units; "
                     "empty range means no ideal (history-only).",
        "confidence_none": dict(NONE_REASONS),
    }


def main(csv_path=CSV_PATH, out_path=OUT_PATH):
    entries = build_entries(csv_path)
    doc = {"_meta": build_meta()}
    for k in sorted(entries):
        doc[k] = entries[k]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    return out_path


if __name__ == "__main__":
    path = main()
    print(f"wrote {path}")
