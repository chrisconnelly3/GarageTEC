import pytest

from store.models import Player
from metrics.context import MetricContext, build_context
from metrics.registry import MetricDef, register, all_defs, REGISTRY
from metrics.tests.conftest import seed_swing
from store import repo


def test_build_context_computes_ppi_from_address_shoulders(db):
    # address shoulders 100px apart; height 72 -> ppi = 100 / (0.24*72)
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[
            (0, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                 "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
                 "nose": (500.0, 120.0)}),
            (10, {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
                  "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
                  "nose": (500.0, 120.0)}),
        ],
        moments=[("address", "face_on", 0), ("top", "face_on", 10)],
    )
    ctx = build_context(db, sw)
    assert ctx.ppi == pytest.approx(100.0 / (0.24 * 72.0), abs=1e-6)
    assert ctx.player.height_in == 72.0
    assert ctx.frame_index_for("face_on", "address") == 0
    assert ctx.frame_index_for("face_on", "top") == 10
    # pose accessor returns the landmark list at that frame
    pose = ctx.pose_at("face_on", "address")
    from metrics.geometry import pick
    assert pick(pose, "nose").x == 500.0


def test_frame_index_for_missing_kind_returns_none(db):
    sw = seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, {"left_shoulder": (450.0, 200.0),
                             "right_shoulder": (550.0, 200.0)})],
        moments=[("address", "face_on", 0)],
    )
    ctx = build_context(db, sw)
    assert ctx.frame_index_for("face_on", "impact") is None
    assert ctx.pose_at("face_on", "impact") is None


def test_registry_register_and_all_defs():
    before = len(REGISTRY)
    d = MetricDef(name="dummy_test_metric", view="face_on",
                  contexts=("address",), fn=lambda ctx: [])
    register(d)
    assert d in all_defs()
    assert len(REGISTRY) == before + 1
    REGISTRY.remove(d)  # keep global registry clean for other tests
