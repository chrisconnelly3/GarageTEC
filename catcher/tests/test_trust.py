from catcher import trust


# A full OpenFlight `shot` payload (the inner dict of the Socket.IO "shot" event),
# with every field measured and high-confidence.
FULL = {
    "ball_speed_mph": 148.2,
    "club_speed_mph": 102.1,
    "estimated_carry_yards": 232,
    "carry_range": [228, 236],
    "launch_angle_vertical": 13.8,
    "launch_angle_vertical_confidence": 0.92,
    "launch_angle_vertical_source": "iwr6843",
    "launch_angle_horizontal": 1.2,
    "launch_angle_horizontal_confidence": 0.88,
    "launch_angle_horizontal_source": "iwr6843",
    "spin_rpm": 2710,
    "spin_rpm_measured": 2710,
    "spin_confidence": 0.81,
    "spin_source": "rolling_buffer",
    "spin_axis_deg": -6.4,
    "club_path_deg": 2.1,
}


def test_all_measured_when_confident():
    t = trust.derive_tiers(FULL)
    assert t["ball_speed"] == trust.MEASURED
    assert t["club_speed"] == trust.MEASURED
    assert t["vla"] == trust.MEASURED
    assert t["hla"] == trust.MEASURED
    assert t["total_spin"] == trust.MEASURED
    assert t["spin_axis"] == trust.MEASURED
    assert t["carry"] == trust.MEASURED


def test_spin_without_measured_twin_is_estimated():
    """spin_rpm present but spin_rpm_measured None => the value is modelled."""
    payload = dict(FULL, spin_rpm=2500, spin_rpm_measured=None)
    t = trust.derive_tiers(payload)
    assert t["total_spin"] == trust.ESTIMATED
    assert t["back_spin"] == trust.ESTIMATED
    assert t["side_spin"] == trust.ESTIMATED


def test_low_confidence_is_estimated():
    payload = dict(FULL, launch_angle_vertical_confidence=0.4)
    assert trust.derive_tiers(payload)["vla"] == trust.ESTIMATED


def test_none_is_absent():
    payload = dict(FULL, club_speed_mph=None, spin_axis_deg=None)
    t = trust.derive_tiers(payload)
    assert t["club_speed"] == trust.ABSENT
    assert t["spin_axis"] == trust.ABSENT


def test_carry_inherits_launch_angle_tier():
    """Carry is always model-derived; it is only as good as the launch angle."""
    payload = dict(FULL, launch_angle_vertical_confidence=0.1)
    assert trust.derive_tiers(payload)["carry"] == trust.ESTIMATED


def test_club_path_always_estimated():
    """OpenFlight documents club path as experimental."""
    assert trust.derive_tiers(FULL)["club_path"] == trust.ESTIMATED


def test_fields_openflight_never_produces_are_absent():
    t = trust.derive_tiers(FULL)
    assert t["attack_angle"] == trust.ABSENT
    assert t["face_to_target"] == trust.ABSENT


def test_no_enrichment_falls_back_conservatively():
    t = trust.derive_tiers(None, device_id="OpenFlight")
    assert t["ball_speed"] == trust.MEASURED
    assert t["carry"] == trust.MEASURED
    assert t["vla"] == trust.ESTIMATED
    assert t["total_spin"] == trust.ESTIMATED
    assert t["attack_angle"] == trust.ABSENT


def test_no_enrichment_trusts_a_non_fabricating_device():
    """The R50 only reports what it measured, so nothing is downgraded."""
    t = trust.derive_tiers(None, device_id="GARMIN-R50")
    assert t["vla"] == trust.MEASURED
    assert t["total_spin"] == trust.MEASURED
    assert t["attack_angle"] == trust.MEASURED
    assert t["face_to_target"] == trust.MEASURED


def test_no_enrichment_is_conservative_for_a_fabricating_device():
    """OpenFlight without its side channel: we cannot tell guesses from data."""
    t = trust.derive_tiers(None, device_id="OpenFlight")
    assert t["vla"] == trust.ESTIMATED
    assert t["total_spin"] == trust.ESTIMATED
    assert t["attack_angle"] == trust.ABSENT


def test_unknown_device_is_trusted_by_default():
    """A device we have no profile for is assumed honest, not assumed to lie."""
    assert trust.derive_tiers(None, device_id=None)["vla"] == trust.MEASURED


def test_schema_drift_does_not_crash():
    """Unknown/renamed keys must degrade, never raise."""
    t = trust.derive_tiers({"ball_speed_mph": 100.0, "totally_new_key": 1})
    assert t["ball_speed"] == trust.MEASURED
    assert t["vla"] == trust.ABSENT


def test_profile_for_openflight_zeroes():
    p = trust.profile_for("OpenFlight")
    assert "hla" in p.zero_means_absent
    assert "attack_angle" in p.zero_means_absent


def test_unknown_device_gets_permissive_profile():
    """An R50 (or any future device) must not have its zeros nulled."""
    p = trust.profile_for("GARMIN-R50")
    assert p.zero_means_absent == frozenset()


def test_model_source_forces_estimated_despite_high_confidence():
    payload = dict(FULL, launch_angle_vertical_source="model_v2",
                   launch_angle_vertical_confidence=0.99)
    assert trust.derive_tiers(payload)["vla"] == trust.ESTIMATED


def test_source_matching_is_case_insensitive():
    payload = dict(FULL, launch_angle_vertical_source="MODEL")
    assert trust.derive_tiers(payload)["vla"] == trust.ESTIMATED


def test_unrecognized_source_does_not_force_estimated():
    """A renamed upstream source must degrade gracefully, not mislabel."""
    payload = dict(FULL, launch_angle_vertical_source="brand_new_sensor")
    assert trust.derive_tiers(payload)["vla"] == trust.MEASURED


def test_missing_confidence_fails_safe_for_scored_fields():
    payload = dict(FULL, launch_angle_vertical_confidence=None,
                   spin_confidence=None)
    t = trust.derive_tiers(payload)
    assert t["vla"] == trust.ESTIMATED
    assert t["total_spin"] == trust.ESTIMATED
    # Fields with no confidence concept are unaffected.
    assert t["ball_speed"] == trust.MEASURED
    assert t["spin_axis"] == trust.MEASURED


def test_missing_carry_is_absent():
    payload = {k: v for k, v in FULL.items() if k != "estimated_carry_yards"}
    assert trust.derive_tiers(payload)["carry"] == trust.ABSENT


def test_missing_club_path_is_absent():
    payload = {k: v for k, v in FULL.items() if k != "club_path_deg"}
    assert trust.derive_tiers(payload)["club_path"] == trust.ABSENT
