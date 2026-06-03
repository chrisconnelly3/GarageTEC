import math

import pytest

from store.models import Landmark
from metrics import geometry as g


def _lm(name, x, y):
    return Landmark(name=name, x=x, y=y, z=0.0, visibility=1.0)


def test_pick_finds_by_name():
    lms = [_lm("nose", 1.0, 2.0), _lm("left_hip", 3.0, 4.0)]
    assert g.pick(lms, "left_hip").x == 3.0
    assert g.pick(lms, "missing") is None


def test_midpoint():
    a, b = _lm("a", 0.0, 0.0), _lm("b", 10.0, 4.0)
    assert g.midpoint(a, b) == (5.0, 2.0)


def test_line_angle_vs_horizontal_level_is_zero():
    # two points at the same image-y -> 0 degrees
    a, b = _lm("ls", 100.0, 50.0), _lm("rs", 200.0, 50.0)
    assert abs(g.line_angle_vs_horizontal(a, b)) < 1e-9


def test_line_angle_vs_horizontal_45_up():
    # image y grows downward; right point 100px higher (smaller y) -> +45 deg
    a, b = _lm("ls", 100.0, 150.0), _lm("rs", 200.0, 50.0)
    assert g.line_angle_vs_horizontal(a, b) == pytest.approx(45.0, abs=1e-6)


def test_line_angle_vs_vertical_plumb_is_zero():
    # a vertical torso (same x) -> 0 deg from vertical
    top, bot = _lm("sh", 100.0, 50.0), _lm("hip", 100.0, 250.0)
    assert abs(g.line_angle_vs_vertical(top, bot)) < 1e-9


def test_line_angle_vs_vertical_30_lean():
    # leaned forward: dx = 200*tan(30) over dy=200
    dx = 200.0 * math.tan(math.radians(30.0))
    top, bot = _lm("sh", 100.0 + dx, 50.0), _lm("hip", 100.0, 250.0)
    assert g.line_angle_vs_vertical(top, bot) == pytest.approx(30.0, abs=1e-6)


def test_lateral_displacement_signed():
    # +x movement of 60 px
    assert g.lateral_displacement((100.0, 50.0), (160.0, 90.0)) == 60.0


def test_forward_vertical_displacement():
    fwd, vert = g.forward_vertical_displacement((100.0, 200.0), (130.0, 160.0))
    assert fwd == 30.0       # dx
    assert vert == -40.0     # dy (image y decreased -> stood up)


def test_ppi_from_height():
    # shoulder_px=100, height=72 -> real_shoulder_in=17.28 -> ppi ~5.787
    ppi = g.ppi_from_height(100.0, 72.0)
    assert ppi == pytest.approx(100.0 / (0.24 * 72.0), abs=1e-9)


def test_foreshortening_full_width_is_zero_turn():
    assert g.foreshortening_to_rotation_deg(100.0, 100.0) == pytest.approx(0.0, abs=1e-9)


def test_foreshortening_half_width_is_arccos_half():
    # width halved -> arccos(0.5) = 60 degrees
    assert g.foreshortening_to_rotation_deg(50.0, 100.0) == pytest.approx(60.0, abs=1e-6)


def test_foreshortening_clamps_over_full_width():
    # current wider than address (noise) -> clamp ratio to 1.0 -> 0 deg
    assert g.foreshortening_to_rotation_deg(130.0, 100.0) == pytest.approx(0.0, abs=1e-9)


def test_foreshortening_zero_address_width_returns_zero():
    assert g.foreshortening_to_rotation_deg(50.0, 0.0) == 0.0
