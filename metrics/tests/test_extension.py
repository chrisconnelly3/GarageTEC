import pytest

from metrics.context import build_context
from metrics.defs import extension
from metrics.tests.conftest import seed_swing


def _ctx(db):
    # ppi = 100/(0.24*72) = 5.78704 px/in. Hip center moves +3in forward (+x)
    # and 4in up (-y) by impact -> magnitude 5in. A mid frame moves 6/8 -> 10in
    # magnitude (the max). Address shoulders 100px for ppi.
    ppi = 100.0 / (0.24 * 72.0)
    base = {"left_shoulder": (600.0, 300.0), "right_shoulder": (700.0, 300.0),
            "left_hip": (640.0, 500.0), "right_hip": (660.0, 500.0)}

    def shifted(fwd_in, up_in):
        c = dict(base)
        dx, dy = fwd_in * ppi, -up_in * ppi
        c["left_hip"] = (640.0 + dx, 500.0 + dy)
        c["right_hip"] = (660.0 + dx, 500.0 + dy)
        return c

    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0)})],
        down_line_frames=[
            (0, base),
            (10, shifted(6.0, 8.0)),   # magnitude 10in (the MAX)
            (20, shifted(3.0, 4.0)),   # impact -> magnitude 5in
        ],
        moments=[("address", "face_on", 0),
                 ("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    return build_context(db, sw)


def test_early_extension_impact_and_max(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in extension.early_extension(ctx)}
    assert by_ctx["impact"].value == pytest.approx(5.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "early_extension_in"
    assert by_ctx["max"].value == pytest.approx(10.0, abs=1e-3)


def test_early_extension_needs_ppi(db):
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(0, {"left_hip": (640.0, 500.0),
                              "right_hip": (660.0, 500.0)}),
                          (20, {"left_hip": (700.0, 460.0),
                               "right_hip": (720.0, 460.0)})],
        moments=[("address", "down_line", 0), ("impact", "down_line", 20)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == 0.0
    assert extension.early_extension(ctx) == []
