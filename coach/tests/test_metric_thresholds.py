from coach import metric_thresholds as mt


def test_match_zones():
    assert mt.zone_for("spine_angle_deg", 18.0, 17.0) == "green"   # |+1| <= 1.5
    assert mt.zone_for("spine_angle_deg", 20.0, 17.0) == "yellow"  # |+3| in (1.5,3]
    assert mt.zone_for("spine_angle_deg", 21.0, 17.0) == "red"     # |+4| > 3


def test_higher_is_better_above_target_is_green():
    assert mt.zone_for("ball_speed", 171.0, 167.0) == "green"   # above tour
    assert mt.zone_for("ball_speed", 166.0, 167.0) == "green"   # 1 below <= 1.5
    assert mt.zone_for("ball_speed", 164.0, 167.0) == "yellow"  # 3 below in (1.5,3.5]
    assert mt.zone_for("ball_speed", 162.0, 167.0) == "red"     # 5 below > 3.5


def test_lower_is_better_below_target_is_green():
    # early_extension_in keeps "lower" semantics (less is better, 0 is ideal).
    assert mt.zone_for("early_extension_in", 0.0, 0.0) == "green"  # at ideal
    assert mt.zone_for("early_extension_in", 0.4, 0.0) == "green"  # +0.4 <= 0.5
    assert mt.zone_for("early_extension_in", 1.0, 0.0) == "yellow" # +1.0 in (0.5,1.2]
    assert mt.zone_for("early_extension_in", 1.5, 0.0) == "red"    # +1.5 > 1.2


def test_directional_hip_sway_match_against_signed_target():
    # DIRECTIONAL: hip target is POSITIVE (pros shift toward target). green<=0.5.
    # Proper shift ~= tour at impact (1.6) -> green.
    assert mt.zone_for("hip_sway_in", 1.6, 1.6) == "green"
    assert mt.zone_for("hip_sway_in", 1.3, 1.6) == "green"   # 0.3 short, ok
    # Over-slide toward target -> red.
    assert mt.zone_for("hip_sway_in", 3.0, 1.6) == "red"     # +1.4 out
    # Partial shift -> yellow.
    assert mt.zone_for("hip_sway_in", 0.8, 1.6) == "yellow"  # 0.8 in (0.5,1.2]
    # Wrong way (slid AWAY from target -> negative) -> red.
    assert mt.zone_for("hip_sway_in", -1.0, 1.6) == "red"    # 2.6 out


def test_directional_head_sway_match_against_signed_target():
    # DIRECTIONAL: head target is NEGATIVE (good trail-side load). green<=1.5.
    # Good trail-side load ~= tour magnitude -> green.
    assert mt.zone_for("head_sway_in", -4.5, -4.5) == "green"
    assert mt.zone_for("head_sway_in", -3.5, -4.5) == "green"  # |1.0| ok
    # Sliding the OPPOSITE way (toward target at top) -> red.
    assert mt.zone_for("head_sway_in", 4.5, -4.5) == "red"     # |9| out
    # No load at all -> red (too little good-direction movement).
    assert mt.zone_for("head_sway_in", 0.0, -4.5) == "red"     # |4.5| out


def test_unknown_metric_or_missing_target_is_none():
    assert mt.zone_for("hand_depth_in", 13.0, None) is None
    assert mt.zone_for("not_a_metric", 1.0, 2.0) is None


def test_direction_lookup():
    assert mt.direction_for("ball_speed") == "higher"
    # sway is now directional via "match" against a signed target (was "lower").
    assert mt.direction_for("hip_sway_in") == "match"
    assert mt.direction_for("head_sway_in") == "match"
    assert mt.direction_for("early_extension_in") == "lower"
    assert mt.direction_for("spine_angle_deg") == "match"
    assert mt.direction_for("hand_depth_in") is None
