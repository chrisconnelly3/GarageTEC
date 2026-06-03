import pytest

from metrics.context import build_context
from metrics.defs import tilt
from metrics.tests.conftest import seed_swing


def _ctx_for_tilt(db):
    # address: shoulders level (0 deg), hips level (0 deg)
    # impact: right shoulder 100px higher than left over 100px run -> +45 deg
    #         hips level still (0 deg)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                 "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}),
            (20, {"left_shoulder": (450.0, 250.0), "right_shoulder": (550.0, 150.0),
                  "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0)}),
        ],
        moments=[("address", "face_on", 0), ("impact", "face_on", 20)],
    )
    return build_context(db, sw)


def test_shoulder_tilt_values_and_method(db):
    ctx = _ctx_for_tilt(db)
    metrics = tilt.shoulder_tilt(ctx)
    by_ctx = {m.context: m for m in metrics}
    assert by_ctx["address"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].value == pytest.approx(45.0, abs=1e-6)
    assert by_ctx["address"].unit == "deg"
    assert by_ctx["address"].method == "exact"
    assert by_ctx["address"].name == "shoulder_tilt_deg"
    assert by_ctx["address"].swing_id == ctx.swing_id


def test_hip_tilt_values(db):
    ctx = _ctx_for_tilt(db)
    by_ctx = {m.context: m for m in tilt.hip_tilt(ctx)}
    assert by_ctx["address"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].value == pytest.approx(0.0, abs=1e-6)
    assert by_ctx["impact"].name == "hip_tilt_deg"
    assert by_ctx["impact"].method == "exact"


def test_tilt_skips_missing_moments(db):
    # only address present -> only one row, no crash for top/impact
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 200.0),
                             "right_shoulder": (550.0, 200.0),
                             "left_hip": (470.0, 400.0),
                             "right_hip": (530.0, 400.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    ctxs = {m.context for m in tilt.shoulder_tilt(ctx)}
    assert ctxs == {"address"}
