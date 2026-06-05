from coach import metric_thresholds as mt


def test_match_zones():
    assert mt.zone_for("spine_angle_deg", 18.0, 17.0) == "green"   # |+1| <= 3
    assert mt.zone_for("spine_angle_deg", 22.0, 17.0) == "yellow"  # |+5| in (3,6]
    assert mt.zone_for("spine_angle_deg", 25.0, 17.0) == "red"     # |+8| > 6


def test_higher_is_better_above_target_is_green():
    assert mt.zone_for("ball_speed", 171.0, 167.0) == "green"   # above tour
    assert mt.zone_for("ball_speed", 165.0, 167.0) == "green"   # 2 below
    assert mt.zone_for("ball_speed", 163.0, 167.0) == "yellow"  # 4 below
    assert mt.zone_for("ball_speed", 160.0, 167.0) == "red"     # 7 below


def test_lower_is_better_below_target_is_green():
    assert mt.zone_for("hip_sway_in", 1.0, 1.6) == "green"    # below tour
    assert mt.zone_for("hip_sway_in", 2.0, 1.6) == "green"    # +0.4
    assert mt.zone_for("hip_sway_in", 2.8, 1.6) == "yellow"   # +1.2
    assert mt.zone_for("hip_sway_in", 3.5, 1.6) == "red"      # +1.9


def test_range_uses_absolute_distance_from_midpoint():
    assert mt.zone_for("head_sway_in", 4.0, 4.5) == "green"
    assert mt.zone_for("head_sway_in", 7.0, 4.5) == "yellow"  # 2.5 out
    assert mt.zone_for("head_sway_in", 8.5, 4.5) == "red"     # 4 out


def test_unknown_metric_or_missing_target_is_none():
    assert mt.zone_for("hand_depth_in", 13.0, None) is None
    assert mt.zone_for("not_a_metric", 1.0, 2.0) is None


def test_direction_lookup():
    assert mt.direction_for("ball_speed") == "higher"
    assert mt.direction_for("hip_sway_in") == "lower"
    assert mt.direction_for("spine_angle_deg") == "match"
    assert mt.direction_for("hand_depth_in") is None
