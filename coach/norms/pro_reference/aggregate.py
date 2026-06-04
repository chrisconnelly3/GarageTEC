"""Aggregate per-swing records (records.jsonl) into pro_reference.json.

Groups every "<metric>@<phase>" value across all extracted tour-pro swings and
emits per-phase percentile bands (p10/p25/p50/p75/p90 + n), in a schema that
mirrors coach/norms/norms.json so it can later layer in as the "ideal" tier.

Confidence tiers:
  * EXACT angle metrics (shoulder_tilt_deg, hip_tilt_deg, spine_angle_deg) ->
    confidence "high" once n is sufficient: a real tour-pro reference in our
    exact metric definitions.
  * SCALE-FREE sway (hip_sway_sw, head_sway_sw, units = fraction of shoulder
    width) -> confidence "provisional": needs the matching amateur-side
    redefinition before it is comparable in-app.

Stdlib only (json, math, statistics-free).
"""
import json
import math
import os
from collections import defaultdict
from typing import Dict, List

OUT_PATH = os.path.join(os.path.dirname(__file__), "pro_reference.json")

EXACT_ANGLE_METRICS = {"shoulder_tilt_deg", "hip_tilt_deg", "spine_angle_deg"}
SCALEFREE_METRICS = {"hip_sway_sw", "head_sway_sw"}

# Horizontal-line tilt metrics (line_angle_vs_horizontal) are SIGNED and
# orientation-dependent: GolfDB clips vary in handedness, camera side and
# facing, so the raw angle wraps near +/-180. Fold each value to its acute
# magnitude from horizontal [0,90] -- orientation-robust, and identical to the
# small raw value for our own consistently-filmed (single-orientation) clips.
# (spine_angle_deg uses line_angle_vs_vertical, already a [0,90] magnitude.)
TILT_FOLD_METRICS = {"shoulder_tilt_deg", "hip_tilt_deg"}


def acute_from_horizontal(angle: float) -> float:
    """Fold an undirected line angle (deg) to its acute magnitude from
    horizontal, in [0, 90]."""
    a = angle % 180.0
    return 180.0 - a if a > 90.0 else a

UNITS = {
    "shoulder_tilt_deg": "deg", "hip_tilt_deg": "deg", "spine_angle_deg": "deg",
    "hip_sway_sw": "fraction_shoulder_width",
    "head_sway_sw": "fraction_shoulder_width",
}

# Min surviving n for an EXACT angle band to be "high" confidence.
MIN_N_HIGH = 20

SOURCE_LINE = (
    "GolfDB (wmcnally/golfdb, CC BY-NC) tour-pro swings, computed in our exact "
    "metric definitions via MediaPipe pose at the shipped address/top/impact "
    "event frames. https://github.com/wmcnally/golfdb"
)


def _percentile(sorted_vals, p):
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(math.floor(k))
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _winsorize(vals: List[float]) -> List[float]:
    """Clip to [p1, p99] to tame pose-glitch outliers; only when n is large
    enough for the tails to be meaningful."""
    if len(vals) < 40:
        return vals
    s = sorted(vals)
    lo, hi = _percentile(s, 0.01), _percentile(s, 0.99)
    return [min(max(v, lo), hi) for v in vals]


def load_records(records_path: str) -> List[Dict]:
    out = []
    with open(records_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _bands(values: List[float]) -> Dict:
    s = sorted(values)
    return {
        "range": [round(_percentile(s, 0.10), 2), round(_percentile(s, 0.90), 2)],
        "p25_p75": [round(_percentile(s, 0.25), 2), round(_percentile(s, 0.75), 2)],
        "median": round(_percentile(s, 0.50), 2),
        "n": len(s),
    }


def aggregate(records: List[Dict]) -> Dict:
    """records -> {metric: {units, confidence, source, contexts:{phase: band}}}"""
    # collect: metric -> phase -> [values]
    buckets: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    n_swings_by_view = defaultdict(set)
    for rec in records:
        n_swings_by_view[rec["view"]].add(rec["id"])
        for key, val in rec["metrics"].items():
            metric, phase = key.split("@")
            val = float(val)
            if metric in TILT_FOLD_METRICS:
                val = acute_from_horizontal(val)
            buckets[metric][phase].append(val)

    entries: Dict[str, Dict] = {}
    for metric, phases in buckets.items():
        contexts = {}
        for phase, vals in phases.items():
            vals = _winsorize(vals)
            contexts[phase] = _bands(vals)
        max_n = max((c["n"] for c in contexts.values()), default=0)
        if metric in EXACT_ANGLE_METRICS:
            confidence = "high" if max_n >= MIN_N_HIGH else "low"
            comment = ("Tour-pro reference (ideal tier) in our exact metric "
                       "definition. Per-phase p10-p90 under 'contexts'.")
            if metric in TILT_FOLD_METRICS:
                comment += (" Reported as acute tilt MAGNITUDE from horizontal "
                            "[0,90] (orientation-normalized across GolfDB's "
                            "mixed handedness/camera-side); compare the app's "
                            "value as |tilt|.")
        else:  # scale-free
            confidence = "provisional"
            comment = ("Tour-pro sway as a fraction of address shoulder width "
                       "(scale-free). PROVISIONAL: needs the matching "
                       "amateur-side %-shoulder-width redefinition before "
                       "in-app comparison.")
        lows = [c["range"][0] for c in contexts.values()]
        highs = [c["range"][1] for c in contexts.values()]
        entries[metric] = {
            "range": [min(lows), max(highs)] if contexts else [],
            "units": UNITS.get(metric, "deg"),
            "tier": "pro_ideal",
            "source": SOURCE_LINE,
            "confidence": confidence,
            "contexts": dict(sorted(contexts.items())),
            "comment": comment,
        }
    entries["_n_swings_by_view"] = {k: len(v) for k, v in n_swings_by_view.items()}
    return entries


def build_meta(records: List[Dict]) -> Dict:
    players = sorted({r["player"] for r in records})
    by_view = defaultdict(int)
    for r in records:
        by_view[r["view"]] += 1
    return {
        "status": "Tour-pro reference computed from GolfDB via our pose+metrics",
        "tier": "pro_ideal",
        "note": (
            "The IDEAL tier: per-phase tour-pro bands (p10-p90) computed in our "
            "exact metric definitions from real tour-pro swings. Distinct from "
            "the CaddieSet mixed-skill POPULATION tier in norms.json. EXACT "
            "angle metrics (shoulder_tilt_deg, hip_tilt_deg, spine_angle_deg) "
            "are directly comparable to the app's exact metrics. Sway metrics "
            "are scale-free (fraction of shoulder width) and PROVISIONAL."
        ),
        "attribution": (
            "Derived from GolfDB (wmcnally/golfdb, CC BY-NC, NON-COMMERCIAL). "
            "Only derived numbers are vendored; not the videos or annotation "
            "table. See coach/norms/pro_reference/SOURCE.md."
        ),
        "method": (
            "yt-dlp source download -> native-res bbox crop -> MediaPipe pose "
            "(model_complexity per vision.constants) at shipped GolfDB event "
            "frames (address=event0, top=event3, impact=event5) -> our "
            "metrics.geometry. Pose-quality gate: mean keyframe shoulder/hip "
            "visibility >= 0.5; angle bands winsorized to [p1,p99] when n>=40. "
            "shoulder_tilt_deg/hip_tilt_deg folded to acute magnitude from "
            "horizontal [0,90] to normalize GolfDB's mixed orientation."
        ),
        "n_records": len(records),
        "n_players": len(players),
        "swings_by_view": dict(by_view),
        "players": players,
    }


def main(records_path: str, out_path: str = OUT_PATH) -> str:
    records = load_records(records_path)
    entries = aggregate(records)
    doc = {"_meta": build_meta(records)}
    for k in sorted(entries):
        doc[k] = entries[k]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    return out_path


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--records", required=True)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()
    path = main(args.records, args.out)
    print(f"wrote {path}")
