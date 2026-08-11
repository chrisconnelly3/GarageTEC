from catcher.openflight_enrich import normalize_event, url_for_host


FULL_EVENT = {
    "shot": {
        "ball_speed_mph": 148.2,
        "club_speed_mph": 102.1,
        "estimated_carry_yards": 232,
        "launch_angle_vertical": 13.8,
        "launch_angle_vertical_confidence": 0.92,
        "spin_rpm": 2710,
        "spin_rpm_measured": 2710,
    },
    "stats": {"shot_count": 4},
}


def test_normalize_extracts_inner_shot():
    assert normalize_event(FULL_EVENT)["ball_speed_mph"] == 148.2


def test_normalize_accepts_bare_shot_dict():
    """Tolerate the payload arriving unwrapped."""
    assert normalize_event(FULL_EVENT["shot"])["ball_speed_mph"] == 148.2


def test_normalize_rejects_non_dict():
    assert normalize_event(None) is None
    assert normalize_event([1, 2, 3]) is None
    assert normalize_event("shot") is None


def test_normalize_rejects_shot_without_ball_speed():
    assert normalize_event({"shot": {"club_speed_mph": 90.0}}) is None


def test_schema_drift_keeps_what_it_can():
    """Renamed/removed keys must not crash; ball speed is the only requirement."""
    drifted = {"shot": {"ball_speed_mph": 100.0, "launch_angle_v2": 12.0}}
    out = normalize_event(drifted)
    assert out["ball_speed_mph"] == 100.0
    assert "launch_angle_v2" in out


def test_url_for_host_defaults_to_openflight_port():
    assert url_for_host("192.168.1.50") == "http://192.168.1.50:8080"


def test_url_for_host_accepts_explicit_port():
    assert url_for_host("192.168.1.50", 9000) == "http://192.168.1.50:9000"
