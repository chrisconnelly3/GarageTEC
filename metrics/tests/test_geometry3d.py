# metrics/tests/test_geometry3d.py
import math
import numpy as np
from metrics import geometry3d as g3


def test_turn_about_axis_90_degrees():
    up = np.array([0.0, 1.0, 0.0])
    addr = np.array([1.0, 0.0, 0.0])      # shoulder line along target line
    rotated = np.array([0.0, 0.0, 1.0])   # turned 90 deg about vertical
    assert abs(abs(g3.turn_about_axis(addr, rotated, up)) - 90.0) < 1e-6


def test_turn_about_axis_zero_at_address():
    up = np.array([0.0, 1.0, 0.0])
    v = np.array([1.0, 0.0, 0.3])
    assert abs(g3.turn_about_axis(v, v, up)) < 1e-6


def test_tilt_from_vertical_magnitude():
    up = np.array([0.0, 1.0, 0.0])
    # shoulder line 30 deg above horizontal in the X-Y plane
    v = np.array([math.cos(math.radians(30)), math.sin(math.radians(30)), 0.0])
    assert abs(g3.tilt_from_horizontal(v, up) - 30.0) < 1e-6
