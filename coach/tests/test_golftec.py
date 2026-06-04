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
