import pytest

from metrics.context import build_context
from metrics.defs import sway
from metrics.tests.conftest import seed_swing


def _ctx_for_sway(db):
    # height 72, address shoulders 100px -> ppi = 100/(0.24*72) = 5.78704 px/in
    # hip center moves +57.87px from address by impact -> +10.0 in (toward +x).
    # net hip motion top->impact is +x, so +x is "toward target": sign stays +.
    # frames: address(0), mid-burst(10) hip at +28.9px, top(20), impact(30) +57.87px
    ppi = 100.0 / (0.24 * 72.0)
    dx_impact = 10.0 * ppi  # 57.870...
    dx_mid = 12.0 * ppi     # 69.44 -> this is the MAX (bigger than impact)
    base = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
            "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
            "nose": (500.0, 120.0)}

    def shifted(dx):
        c = dict(base)
        c["left_hip"] = (470.0 + dx, 400.0)
        c["right_hip"] = (530.0 + dx, 400.0)
        c["nose"] = (500.0 + dx, 120.0)
        return c

    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, base),
            (10, shifted(dx_mid)),
            (20, shifted(dx_mid * 0.5)),
            (30, shifted(dx_impact)),
        ],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 30)],
    )
    return build_context(db, sw)


def test_hip_sway_inches_and_method(db):
    ctx = _ctx_for_sway(db)
    by_ctx = {m.context: m for m in sway.hip_sway(ctx)}
    assert by_ctx["impact"].value == pytest.approx(10.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "hip_sway_in"
    # max sway picks the frame with largest |dx| (the 12-in mid frame)
    assert by_ctx["max"].value == pytest.approx(12.0, abs=1e-3)


def test_head_sway_inches(db):
    ctx = _ctx_for_sway(db)
    by_ctx = {m.context: m for m in sway.head_sway(ctx)}
    assert by_ctx["impact"].value == pytest.approx(10.0, abs=1e-3)
    assert by_ctx["impact"].name == "head_sway_in"
    assert by_ctx["max"].value == pytest.approx(12.0, abs=1e-3)


def test_sway_zero_when_no_ppi(db):
    # no address moment -> ppi 0 -> sway fns return nothing (cannot convert)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(20, {"left_hip": (470.0, 400.0),
                              "right_hip": (530.0, 400.0),
                              "nose": (500.0, 120.0)})],
        moments=[("top", "face_on", 20)],
    )
    ctx = build_context(db, sw)
    assert sway.hip_sway(ctx) == []
