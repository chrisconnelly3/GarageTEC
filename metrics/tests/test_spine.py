import math

import pytest

from metrics.context import build_context
from metrics.defs import spine
from metrics.tests.conftest import seed_swing


def test_spine_angle_30deg(db):
    # down-line: shoulder center leaned forward 30 deg from the hip center over
    # a 200px vertical drop. dx = 200*tan(30).
    dx = 200.0 * math.tan(math.radians(30.0))
    coords = {
        "left_shoulder": (600.0 + dx, 300.0), "right_shoulder": (600.0 + dx, 300.0),
        "left_hip": (600.0, 500.0), "right_hip": (600.0, 500.0),
    }
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(0, coords), (20, coords)],
        moments=[("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    ctx = build_context(db, sw)
    by_ctx = {m.context: m for m in spine.spine_angle(ctx)}
    assert by_ctx["address"].value == pytest.approx(30.0, abs=1e-6)
    assert by_ctx["address"].unit == "deg"
    assert by_ctx["address"].method == "exact"
    assert by_ctx["address"].name == "spine_angle_deg"


def test_spine_uses_down_line_view_not_face_on(db):
    # face_on present but no down_line -> no rows (spine is a DTL metric)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0),
                             "left_hip": (470.0, 500.0),
                             "right_hip": (530.0, 500.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    assert spine.spine_angle(ctx) == []
