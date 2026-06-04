import math

from coach.norms import build_norms as b


def test_clean_drops_inf_nan_and_none():
    raw = [10.0, float("inf"), float("-inf"), float("nan"), None, 12.0]
    out = b.clean_values(raw)
    assert out == [10.0, 12.0]


def test_clean_drops_exact_clamp_artifacts():
    raw = [0.0, 5.0, 180.0, 7.0, 0.0]
    out = b.clean_values(raw, drop_clamps=(0.0, 180.0))
    assert out == [5.0, 7.0]


def test_clean_winsorizes_extreme_outliers_inward():
    # 100 values 1..100; a stray 100000 should be clipped down to the p99 of
    # the surviving set (not deleted), and the tiny -100000 clipped up to p1.
    raw = [float(i) for i in range(1, 101)] + [100000.0, -100000.0]
    out = b.clean_values(raw)
    assert max(out) < 200.0          # huge outlier pulled in
    assert min(out) > -50.0          # huge negative pulled in
    assert len(out) == 102           # winsorize clips, does not drop rows


def test_clean_empty_returns_empty():
    assert b.clean_values([]) == []
    assert b.clean_values([float("nan"), None]) == []


def test_percentiles_basic():
    vals = [float(i) for i in range(1, 101)]  # 1..100
    p10, med, p90 = b.percentiles(vals)
    assert abs(p10 - 10.9) < 0.5
    assert abs(med - 50.5) < 0.5
    assert abs(p90 - 90.1) < 0.5


def test_percentiles_empty_is_none():
    assert b.percentiles([]) is None


def test_convert_none_is_identity():
    assert b.convert(11.16, "none") == 11.16


def test_convert_vertical_from_horizontal():
    # CaddieSet spine 70.53 deg vs horizontal -> 19.47 deg vs vertical (ours)
    assert abs(b.convert(70.53, "vertical_from_horizontal") - 19.47) < 1e-9


import os

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "tiny_caddieset.csv")

MAPPED = {"shoulder_tilt_deg", "spine_angle_deg"}
NONE_METRICS = {
    "hip_tilt_deg", "shoulder_turn_deg", "hip_turn_deg",
    "hip_sway_in", "head_sway_in", "early_extension_in", "hand_depth_in",
}


def test_mapping_covers_all_nine_metrics_exactly():
    metrics = {m for (m, _ctx) in b.MAPPING} | b.NONE_REASONS.keys()
    assert metrics == MAPPED | NONE_METRICS
    assert len(MAPPED | NONE_METRICS) == 9


def test_build_entries_mapped_metrics_have_bands():
    entries = b.build_entries(FIX)
    st = entries["shoulder_tilt_deg"]
    assert st["confidence"] == "medium"
    assert st["units"] == "deg"
    assert "CaddieSet" in st["source"] and "NOT a validated ideal" in st["source"]
    low, high = st["range"]
    assert low < high
    # top-level range is the union across contexts; low comes from the address
    # block (10..20 -> p10 ~10.9), high from the top block (20..30 -> p90 ~29.1).
    assert abs(low - 10.9) < 0.6
    assert abs(high - 29.1) < 0.6
    # the address context band itself is the 10..20 block: p10/p90 ~10.9/19.1
    addr_low, addr_high = st["contexts"]["address"]["range"]
    assert abs(addr_low - 10.9) < 0.6
    assert abs(addr_high - 19.1) < 0.6
    # per-context bands recorded under "contexts"
    assert set(st["contexts"]) == {"address", "top", "impact"}


def test_build_entries_spine_conversion_applied_and_ascending():
    entries = b.build_entries(FIX)
    sp = entries["spine_angle_deg"]
    assert sp["confidence"] == "medium"
    # 0-SPINE-ANGLE 70..80 vs horizontal -> 90-x = 10..20 vs vertical
    low, high = sp["contexts"]["address"]["range"]
    assert low < high                      # ascending after the 90-x flip
    assert abs(low - 10.9) < 0.6
    assert abs(high - 19.1) < 0.6
    # top has NO spine feature in CaddieSet -> not in contexts
    assert "top" not in sp["contexts"]
    assert "impact" in sp["contexts"] and "address" in sp["contexts"]


def test_build_entries_none_metrics_are_history_only():
    entries = b.build_entries(FIX)
    for m in NONE_METRICS:
        e = entries[m]
        assert e["confidence"] == "none"
        assert e["range"] == []
        assert e["reason"]            # documented why


def test_meta_has_disclaimer_and_none_list():
    meta = b.build_meta()
    text = (meta["status"] + " " + meta["note"]).lower()
    assert "human" in text or "curated" in text     # keeps test_norms happy
    assert "not" in meta["note"].lower() and "ideal" in meta["note"].lower()
    assert "CaddieSet" in meta["attribution"]
    # every confidence:none metric is listed with a reason
    for m in NONE_METRICS:
        assert m in meta["confidence_none"]


def test_main_writes_deterministically(tmp_path):
    out = tmp_path / "norms.json"
    p1 = b.main(csv_path=FIX, out_path=str(out))
    first = out.read_text(encoding="utf-8")
    p2 = b.main(csv_path=FIX, out_path=str(out))
    second = out.read_text(encoding="utf-8")
    assert p1 == p2 == str(out)
    # deterministic except the generated date line, which we blank for the diff
    import re
    norm = lambda s: re.sub(r'"generated":\s*"[^"]*"', '"generated":"X"', s)
    assert norm(first) == norm(second)
