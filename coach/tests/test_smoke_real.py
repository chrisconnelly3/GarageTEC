import os
import importlib.util

import pytest

from store import db as dbmod
from store import repo
from store.models import Metric, Shot
from coach import coach
from coach.backend import make_backend

_GATE = (
    os.environ.get("COACH_RUN_REAL") == "1"
    and importlib.util.find_spec("anthropic") is not None
    and bool(os.environ.get("ANTHROPIC_API_KEY"))
)

pytestmark = pytest.mark.skipif(
    not _GATE,
    reason="real backend smoke test: set COACH_RUN_REAL=1, install anthropic, "
           "and provide ANTHROPIC_API_KEY to run",
)


def test_real_cloud_backend_smoke():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    try:
        pid = repo.get_or_create_player(conn, "Smoke", 72.0, "R").id
        sid = repo.create_session(conn, pid).id
        sw = repo.add_swing(conn, sid, pid, "v.MOV", club="7i")
        repo.save_metrics(conn, sw.id, [
            Metric(sw.id, "hip_sway_in", "impact", 2.6, "in", "shoulder_ratio"),
        ])
        shot = repo.save_shot(conn, Shot(captured_at="t", player_id=pid,
                                         session_id=sid, ball_speed=119.0,
                                         carry=172.0))
        repo.link_shot_to_swing(conn, shot.id, sw.id)

        backend = make_backend("cloud")
        row = coach.coach_swing(conn, backend, sw.id)
        assert row.id is not None
        assert repo.get_coaching(conn, swing_id=sw.id)
    finally:
        conn.close()
