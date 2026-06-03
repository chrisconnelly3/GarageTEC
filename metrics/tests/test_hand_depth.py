import pytest

from metrics.context import build_context
from metrics.defs import hand_depth
from metrics.tests.conftest import seed_swing


def _ctx(db):
    # ppi from face_on address shoulders 100px, height 72 -> 5.78704 px/in.
    # Down-line: trail shoulder (right_shoulder for a RH golfer) at x=700.
    # mid-wrist x=700 + 4in*ppi at impact -> hand_depth 4in.
    ppi = 100.0 / (0.24 * 72.0)
    dl = {"left_shoulder": (700.0, 300.0), "right_shoulder": (700.0, 300.0),
          "left_wrist": (700.0 + 4.0 * ppi, 450.0),
          "right_wrist": (700.0 + 4.0 * ppi, 450.0),
          "left_hip": (700.0, 500.0), "right_hip": (700.0, 500.0)}
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 300.0),
                             "right_shoulder": (550.0, 300.0)})],
        down_line_frames=[(20, dl), (30, dl)],
        moments=[("address", "face_on", 0),
                 ("top", "down_line", 20), ("impact", "down_line", 30)],
    )
    return build_context(db, sw)


def test_hand_depth_inches(db):
    ctx = _ctx(db)
    by_ctx = {m.context: m for m in hand_depth.hand_depth(ctx)}
    assert by_ctx["impact"].value == pytest.approx(4.0, abs=1e-3)
    assert by_ctx["top"].value == pytest.approx(4.0, abs=1e-3)
    assert by_ctx["impact"].unit == "in"
    assert by_ctx["impact"].method == "shoulder_ratio_0.24"
    assert by_ctx["impact"].name == "hand_depth_in"


def test_hand_depth_skips_without_ppi(db):
    sw = seed_swing(
        db, height_in=72.0,
        down_line_frames=[(30, {"right_shoulder": (700.0, 300.0),
                               "left_shoulder": (700.0, 300.0),
                               "left_wrist": (760.0, 450.0),
                               "right_wrist": (760.0, 450.0)})],
        moments=[("impact", "down_line", 30)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == 0.0
    assert hand_depth.hand_depth(ctx) == []
