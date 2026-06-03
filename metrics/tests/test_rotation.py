import pytest

from metrics.context import build_context
from metrics.defs import rotation
from metrics.tests.conftest import seed_swing

LOW = "foreshortening_2d;confidence=low"


def _ctx(db):
    # address shoulders 100px, hips 60px wide.
    # top: shoulders project to 50px -> arccos(0.5)=60deg; hips to 30px -> 60deg.
    # impact: shoulders back to ~86.6px -> arccos(0.866)=30deg.
    addr = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
            "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}
    top = {"left_shoulder": (475.0, 200.0), "right_shoulder": (525.0, 200.0),
           "left_hip": (485.0, 400.0), "right_hip": (515.0, 400.0)}
    impact = {"left_shoulder": (456.7, 200.0), "right_shoulder": (543.3, 200.0),
              "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, addr), (20, top), (40, impact)],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 40)],
    )
    return build_context(db, sw)


def test_shoulder_turn_estimate_and_low_confidence(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in rotation.shoulder_turn(ctx)}
    assert by_ctx["top"].value == pytest.approx(60.0, abs=0.1)
    assert by_ctx["impact"].value == pytest.approx(30.0, abs=0.2)
    assert by_ctx["top"].unit == "deg"
    assert by_ctx["top"].method == LOW
    assert by_ctx["top"].name == "shoulder_turn_deg"


def test_hip_turn_estimate_and_low_confidence(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in rotation.hip_turn(ctx)}
    assert by_ctx["top"].value == pytest.approx(60.0, abs=0.1)
    assert by_ctx["top"].method == LOW
    assert by_ctx["top"].name == "hip_turn_deg"


def test_rotation_skips_without_address(db):
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(20, {"left_shoulder": (475.0, 200.0),
                             "right_shoulder": (525.0, 200.0)})],
        moments=[("top", "face_on", 20)],
    )
    ctx = build_context(db, sw)
    assert rotation.shoulder_turn(ctx) == []
