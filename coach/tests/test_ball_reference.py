import json
import math

from coach import ball_reference as br


def test_clubs_ordered_driver_to_pw():
    assert br.CLUBS[0] == "Driver" and br.CLUBS[-1] == "PW"
    assert len(br.CLUBS) == 12


def test_benchmark_ball_7_iron_with_smash_derived():
    shot = {"ball_speed": 118.0, "club_speed": 89.0, "attack_angle": -4.0,
            "vla": 16.0, "total_spin": 7200.0, "carry": 170.0}
    rows = br.benchmark_ball(shot, "7 Iron")
    by = {r["key"]: r for r in rows}
    # all 7 R50-reported metrics present, Max Height / Land Angle absent
    assert set(by) == {"ball_speed", "club_speed", "smash", "launch", "spin",
                       "attack_angle", "carry"}
    assert by["ball_speed"]["target"] == 120 and by["ball_speed"]["delta"] == -2.0
    assert by["smash"]["value"] == round(118.0 / 89.0, 2)   # derived
    assert by["spin"]["value"] == 7200.0 and by["spin"]["target"] == 7097
    assert by["carry"]["near"] is True                       # |170-172|=2 <= 10


def test_benchmark_skips_missing_metrics():
    # only ball_speed present -> only ball_speed compared (no club_speed/smash)
    rows = br.benchmark_ball({"ball_speed": 165.0}, "Driver")
    keys = {r["key"] for r in rows}
    assert keys == {"ball_speed"}        # club_speed/smash/etc. need their inputs


def test_benchmark_unknown_club_or_none_shot_is_empty():
    assert br.benchmark_ball({"ball_speed": 100}, "Putter") == []
    assert br.benchmark_ball(None, "Driver") == []
    assert br.benchmark_ball({"ball_speed": 100}, None) == []


def test_near_flag_tolerances():
    shot = {"ball_speed": 167.0, "club_speed": 113.0}   # exact driver speeds
    by = {r["key"]: r for r in br.benchmark_ball(shot, "Driver")}
    assert by["ball_speed"]["near"] is True and by["ball_speed"]["delta"] == 0.0


# ---- raw_ball_fields ----------------------------------------------------

def test_raw_ball_fields_order_and_shape():
    rows = br.raw_ball_fields({"club_path": 2.14, "face_to_target": -1.0,
                               "spin_axis": 0.0, "total_spin": 5000.0})
    assert [r["key"] for r in rows] == [
        "club_path", "face_to_target", "spin_axis", "back_spin", "side_spin", "hla"]
    for r in rows:
        assert set(r) == {"key", "label", "unit", "value"}
    by = {r["key"]: r for r in rows}
    assert by["club_path"]["value"] == 2.1 and by["club_path"]["unit"] == "deg"
    assert by["back_spin"]["unit"] == "rpm"


def test_raw_ball_fields_spin_split_derivation():
    # spin_axis 30deg, total 5000 -> back=5000*cos30, side=5000*sin30
    rows = {r["key"]: r for r in
            br.raw_ball_fields({"total_spin": 5000.0, "spin_axis": 30.0})}
    assert rows["back_spin"]["value"] == round(5000.0 * math.cos(math.radians(30)))
    assert rows["side_spin"]["value"] == round(5000.0 * math.sin(math.radians(30)))


def test_raw_ball_fields_prefers_explicit_keys():
    raw = json.dumps({"BallData": {"BackSpin": 6200, "SideSpin": 410}})
    # derived values would differ; explicit BackSpin/SideSpin must win
    rows = {r["key"]: r for r in
            br.raw_ball_fields({"total_spin": 5000.0, "spin_axis": 30.0,
                                "raw_json": raw})}
    assert rows["back_spin"]["value"] == 6200
    assert rows["side_spin"]["value"] == 410


def test_raw_ball_fields_none_inputs_dont_crash():
    rows = {r["key"]: r for r in br.raw_ball_fields(
        {"club_path": None, "spin_axis": None, "total_spin": None})}
    assert rows["club_path"]["value"] is None
    assert rows["back_spin"]["value"] is None and rows["side_spin"]["value"] is None
    # missing total_spin or spin_axis -> derived None
    rows2 = {r["key"]: r for r in br.raw_ball_fields({"total_spin": 5000.0})}
    assert rows2["back_spin"]["value"] is None
    assert br.raw_ball_fields(None) == []


def test_target_for_lookup():
    assert br.target_for("ball_speed", "Driver") == 167
    assert br.target_for("spin", "7 Iron") == 7097
    assert br.target_for("ball_speed", "Putter") is None   # unknown club
    assert br.target_for("nonsense", "Driver") is None     # unknown metric
    assert br.target_for("ball_speed", None) is None


def test_ball_benchmark_has_direction_and_zone():
    shot = {"ball_speed": 171.0, "club_speed": 115.0, "vla": 12.2,
            "total_spin": 3450, "attack_angle": 1.5, "carry": 281.0}
    rows = {r["key"]: r for r in br.benchmark_ball(shot, "Driver")}
    assert rows["ball_speed"]["direction"] == "higher"
    assert rows["ball_speed"]["zone"] == "green"      # above tour
    assert rows["spin"]["direction"] == "match"
    assert rows["spin"]["zone"] == "red"              # 3450 vs 2686, way over


def test_raw_ball_fields_includes_hla():
    raw = {r["key"]: r for r in br.raw_ball_fields({"hla": 0.8})}
    assert raw["hla"]["value"] == 0.8 and raw["hla"]["unit"] == "deg"
