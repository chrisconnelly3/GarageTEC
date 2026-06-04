"""Generate golftec_reference.json — the AUTHORITATIVE tour-pro ideal tier.

Per the user's decision (2026-06-04): GolfTEC's published numbers are trusted
OVER our GolfDB-deduced numbers wherever they conflict. So GolfTEC is the
PRIMARY "ideal" reference; the GolfDB-computed pro_reference.json is SECONDARY
(it fills metrics GolfTEC doesn't publish -- head sway, hand depth -- and
supplies a 2D-measured pro baseline + variability bands).

Two GolfTEC sources, hand-transcribed with provenance:
  * "Tour Averages" chart (150+ PGA/Senior PGA/LPGA/mini-tour players, with
    HealthSouth) -- full address/top/impact/finish table, degrees, 3D, signed
    by direction.
  * "SwingTRU Motion Study" (13,000+ golfers, pro -> 30-hcp) -- newer, larger;
    used preferentially where it overlaps.

CRITICAL CAVEAT baked into every entry: GolfTEC numbers are 3D. Our app measures
2D. A 2D measurement only equals the 3D value when the body segment is SQUARE to
the camera (≈ address for face-on); once the torso rotates (top, impact) the 2D
projection foreshortens and under-reads. So each (metric, phase) carries
`two_d_comparable_now` -- whether the current 2D app can be compared to this
GolfTEC target as-is, or whether it needs the deferred 3D (two-camera) path.

Stdlib only.
"""
import datetime
import json
import os

OUT_PATH = os.path.join(os.path.dirname(__file__), "golftec_reference.json")

TOUR_AVG = ("GolfTEC Tour Averages (150+ PGA/Senior PGA/LPGA/mini-tour players, "
            "with HealthSouth); 3D body measurement.")
SWINGTRU = ("GolfTEC SwingTRU Motion Study (13,000+ golfers, pro to 30-handicap; "
            "OptiMotion-class 3D). https://www.golftec.ca/swingtru")

# Per (our_metric -> per-phase entry). value in `units`; `dir` = GolfTEC's
# directional label; `c2d` = two_d_comparable_now (square enough for our 2D app
# to compare today); `src` = which GolfTEC source. needs_3d = not c2d.
# Phases use GolfTEC's chart: address / top / impact / finish.
GOLFTEC = {
    "shoulder_tilt_deg": {
        "units": "deg", "note": "shoulder-line tilt from horizontal (side-bend)",
        "phases": {
            "address": {"value": 10, "dir": "trail(right) shoulder down", "c2d": True,  "src": TOUR_AVG},
            "top":     {"value": 36, "dir": "lead(left) shoulder down",   "c2d": False, "src": SWINGTRU},
            "impact":  {"value": 39, "dir": "trail(right) shoulder down",  "c2d": False, "src": SWINGTRU},
            "finish":  {"value": 15, "dir": "trail(right) shoulder down",  "c2d": False, "src": TOUR_AVG},
        },
    },
    "hip_tilt_deg": {
        "units": "deg", "note": "pelvis-line tilt from horizontal (O-factor)",
        "phases": {
            "address": {"value": 0,  "dir": "neutral",            "c2d": True,  "src": TOUR_AVG},
            "top":     {"value": 11, "dir": "lead(left) hip down", "c2d": False, "src": TOUR_AVG},
            "impact":  {"value": 14, "dir": "trail(right) hip down","c2d": False, "src": TOUR_AVG},
            "finish":  {"value": 5,  "dir": "trail(right) hip down","c2d": False, "src": TOUR_AVG},
        },
    },
    "shoulder_turn_deg": {
        "units": "deg", "note": "thorax axial rotation vs target line; 3D-ONLY",
        "needs_3d_all": True,
        "phases": {
            "address": {"value": 5,   "dir": "open",   "c2d": False, "src": TOUR_AVG},
            "top":     {"value": 89,  "dir": "closed", "c2d": False, "src": TOUR_AVG},
            "impact":  {"value": 48,  "dir": "open",   "c2d": False, "src": TOUR_AVG},
            "finish":  {"value": 138, "dir": "open",   "c2d": False, "src": TOUR_AVG},
        },
    },
    "hip_turn_deg": {
        "units": "deg", "note": "pelvis axial rotation vs target line; 3D-ONLY",
        "needs_3d_all": True,
        "phases": {
            "address": {"value": 2,   "dir": "closed", "c2d": False, "src": TOUR_AVG},
            "top":     {"value": 48,  "dir": "closed", "c2d": False, "src": TOUR_AVG},
            "impact":  {"value": 36,  "dir": "open",   "c2d": False, "src": SWINGTRU},
            "finish":  {"value": 106, "dir": "open",   "c2d": False, "src": TOUR_AVG},
        },
    },
    "hip_sway_in": {
        "units": "in", "note": "pelvis lateral translation toward target (+); "
                               "in-plane for face-on so 2D-measurable once our "
                               "definition is reconciled to GolfTEC's",
        "phases": {
            "top":    {"value": 3.9, "dir": "toward target", "c2d": True, "src": SWINGTRU},
            "impact": {"value": 1.6, "dir": "toward target", "c2d": True, "src": SWINGTRU},
        },
    },
    "spine_angle_deg": {
        "units": "deg", "note": "MAPPING NOTE: GolfTEC 'shoulder bend' is thorax "
                               "FORWARD flexion vs vertical; our spine_angle is "
                               "shoulder-center->hip-center lean vs vertical. "
                               "Related, not identical -> mapping_confidence low.",
        "mapping_confidence": "low",
        "phases": {
            "address": {"value": 36, "dir": "forward", "c2d": True,  "src": TOUR_AVG},
            "top":     {"value": 2,  "dir": "forward", "c2d": False, "src": TOUR_AVG},
            "impact":  {"value": 17, "dir": "forward", "c2d": False, "src": TOUR_AVG},
            "finish":  {"value": 32, "dir": "back",    "c2d": False, "src": SWINGTRU},
        },
    },
}

# Metrics GolfTEC does NOT publish -> stay GolfDB-only (pointer, no values here).
GOLFDB_ONLY = {
    "head_sway_in": "No GolfTEC value; see pro_reference.json (GolfDB, provisional).",
    "hand_depth_in": "No GolfTEC value; see pro_reference.json (GolfDB; not yet computed).",
    "early_extension_in": "No GolfTEC magnitude (binary screen: pros ~0% early "
                          "extension); see pro_reference.json / literature.",
}


def build_entries():
    entries = {}
    for metric, spec in GOLFTEC.items():
        contexts = {}
        for phase, p in spec["phases"].items():
            contexts[phase] = {
                "value": p["value"],
                "direction": p["dir"],
                "two_d_comparable_now": p["c2d"],
                "needs_3d": not p["c2d"],
                "source": p["src"],
            }
        e = {
            "value_by_phase": {ph: c["value"] for ph, c in contexts.items()},
            "units": spec["units"],
            "tier": "pro_ideal_golftec",
            "authoritative": True,
            "confidence": "high",
            "source": "GolfTEC (Tour Averages + SwingTRU Motion Study)",
            "note": spec["note"],
            "contexts": contexts,
        }
        if spec.get("needs_3d_all"):
            e["needs_3d_all"] = True
        if spec.get("mapping_confidence"):
            e["mapping_confidence"] = spec["mapping_confidence"]
        entries[metric] = e
    for metric, reason in GOLFDB_ONLY.items():
        entries[metric] = {
            "tier": "golfdb_only",
            "authoritative": False,
            "confidence": "none",
            "source": None,
            "reason": reason,
        }
    return entries


def build_meta():
    return {
        "status": "AUTHORITATIVE tour-pro ideal tier (GolfTEC published numbers)",
        "tier": "pro_ideal_golftec",
        "precedence": ("GolfTEC is trusted OVER our GolfDB-deduced numbers "
                       "wherever they conflict (user decision 2026-06-04). "
                       "pro_reference.json (GolfDB) is secondary: gap-fill + a "
                       "2D-measured pro baseline + variability bands."),
        "critical_2d_vs_3d_caveat": (
            "GolfTEC numbers are 3D. The app measures 2D. A 2D value equals the "
            "3D target only when the segment is square to the camera (≈ address "
            "for face-on); at top/impact the 2D projection foreshortens and "
            "under-reads. Honor each context's `two_d_comparable_now`: compare "
            "the live 2D metric to GolfTEC ONLY where it is true. The rest need "
            "the deferred two-camera 3D path (see handoff: GolfTEC-grade 3D)."
        ),
        "sources": {
            "tour_averages": TOUR_AVG,
            "swingtru": SWINGTRU,
        },
        "generated": datetime.date.today().isoformat(),
        "golfdb_secondary": ("coach/norms/pro_reference/pro_reference.json "
                             "supplies head/hand-depth (no GolfTEC value) and a "
                             "same-projection 2D pro baseline for the rotated-"
                             "position metrics until 3D exists."),
    }


def main(out_path=OUT_PATH):
    entries = build_entries()
    doc = {"_meta": build_meta()}
    for k in sorted(entries):
        doc[k] = entries[k]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    return out_path


if __name__ == "__main__":
    print(f"wrote {main()}")
