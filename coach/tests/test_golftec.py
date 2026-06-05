# coach/tests/test_golftec.py
from coach import golftec


def test_load_golftec_reference_has_turn_target():
    ref = golftec.load()
    assert ref["shoulder_turn_deg"]["value_by_phase"]["top"] == 89


def test_compare_uses_target_when_3d_available():
    ref = golftec.load()
    # shoulder turn @ top is needs_3d -> only comparable when has_3d=True
    r = golftec.compare("shoulder_turn_deg", "top", 80.0, has_3d=True, ref=ref)
    assert r["comparable"] is True
    assert abs(r["delta"] - (80.0 - 89.0)) < 1e-9
    r2 = golftec.compare("shoulder_turn_deg", "top", 80.0, has_3d=False, ref=ref)
    assert r2["comparable"] is False
    assert r2["reason"] == "needs_3d"


def test_compare_square_position_works_in_2d():
    ref = golftec.load()
    # shoulder tilt @ address is two_d_comparable_now -> comparable without 3D
    r = golftec.compare("shoulder_tilt_deg", "address", 12.0, has_3d=False, ref=ref)
    assert r["comparable"] is True
    assert abs(r["target"] - 10.0) < 1e-9


# --- benchmark_metrics (vs-tour-pro panel data) -------------------------------
from coach import golftec


def test_benchmark_2d_square_metric_is_comparable():
    metrics = [{"name": "shoulder_tilt_deg", "context": "address",
                "value": 12.0, "unit": "deg", "method": "exact"}]
    rows = golftec.benchmark_metrics(metrics)
    assert len(rows) == 1
    r = rows[0]
    assert r["comparable"] is True and r["target"] == 10 and r["delta"] == 2.0


def test_benchmark_turn_needs_3d_when_only_2d_present():
    metrics = [{"name": "shoulder_turn_deg", "context": "top",
                "value": 50.0, "unit": "deg", "method": "foreshortening_2d;confidence=low"}]
    rows = golftec.benchmark_metrics(metrics)
    assert len(rows) == 1
    assert rows[0]["comparable"] is False and rows[0]["reason"] == "needs_3d"
    assert rows[0]["target"] == 89 and rows[0]["delta"] is None


def test_benchmark_turn_comparable_with_3d():
    metrics = [{"name": "shoulder_turn_deg", "context": "top",
                "value": 85.0, "unit": "deg", "method": "triangulated_3d;confidence=high"}]
    rows = golftec.benchmark_metrics(metrics)
    assert rows[0]["comparable"] is True and rows[0]["delta"] == -4.0


def test_benchmark_dedup_prefers_comparable_3d_row():
    # same (name, context) with a 2D row (needs_3d) + a 3D row (comparable)
    metrics = [
        {"name": "shoulder_tilt_deg", "context": "impact", "value": 12.0,
         "unit": "deg", "method": "exact"},               # 2D -> needs_3d at impact
        {"name": "shoulder_tilt_deg", "context": "impact", "value": 38.0,
         "unit": "deg", "method": "triangulated_3d"},      # 3D -> comparable
    ]
    rows = golftec.benchmark_metrics(metrics)
    assert len(rows) == 1
    assert rows[0]["comparable"] is True and rows[0]["value"] == 38.0


def test_benchmark_emits_raw_row_for_metrics_without_golftec_target():
    # Previously this asserted an empty list; now unreferenced metrics get a
    # 'raw' row so the UI can still render a card for them.
    metrics = [{"name": "head_sway_in", "context": "impact", "value": 1.0,
                "unit": "in", "method": "shoulder_ratio_0.24"}]
    rows = golftec.benchmark_metrics(metrics)
    assert len(rows) == 1
    r = rows[0]
    assert r["state"] == "raw"
    assert r["target"] is None and r["zone"] is None and r["delta"] is None
    assert r["value"] == 1.0


def test_supplementary_references_merged():
    ref = golftec.load()
    xf = ref["x_factor_deg"]["contexts"]["top"]
    assert xf["value"] == 43 and xf["two_d_comparable_now"] is False
    ee = ref["early_extension_in"]["contexts"]["impact"]
    assert ee["value"] == 0 and ee["two_d_comparable_now"] is True
    hs = ref["head_sway_in"]["contexts"]["top"]
    assert hs["value"] == 4.5 and hs["two_d_comparable_now"] is True
    assert ref["x_factor_stretch_deg"]["contexts"]["downswing"]["value"] == 5
    assert ref["shoulder_tilt_deg"]["contexts"]["address"]["value"] == 10


def test_compare_uses_supplementary_target():
    c = golftec.compare("early_extension_in", "impact", 1.5)
    assert c["comparable"] is True and c["target"] == 0 and c["delta"] == 1.5


def test_benchmark_row_has_zone_and_state_for_comparable():
    metrics = [{"name": "shoulder_tilt_deg", "context": "address",
                "value": 12.0, "unit": "deg", "method": "exact"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "ok"
    assert row["direction"] == "match"
    assert row["zone"] == "green"        # |12-10|=2 <= 3
    assert row["target"] == 10 and row["delta"] == 2.0


def test_benchmark_needs_3d_has_no_zone():
    metrics = [{"name": "shoulder_turn_deg", "context": "top",
                "value": 50.0, "unit": "deg", "method": "foreshortening_2d"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "needs_3d" and row["zone"] is None
    assert row["comparable"] is False and row["target"] == 89


def test_benchmark_emits_raw_row_for_unreferenced_metric():
    metrics = [{"name": "hand_depth_in", "context": "impact",
                "value": 9.2, "unit": "in", "method": "shoulder_ratio_0.24"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "raw"
    assert row["target"] is None and row["zone"] is None and row["delta"] is None
    assert row["value"] == 9.2
