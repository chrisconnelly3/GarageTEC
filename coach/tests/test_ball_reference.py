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
