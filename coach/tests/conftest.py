import json

import pytest

from store import db as dbmod
from store import repo
from store.models import Metric, Shot


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


@pytest.fixture
def seeded(db):
    """A player with a session, a target swing that has metrics + a linked shot,
    plus two prior swings carrying the same metric (history/baseline)."""
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id

    # Two prior swings establishing a baseline for hip_sway_in at impact.
    for v in (1.3, 1.5):
        prior = repo.add_swing(db, sid, pid, "prior.MOV", club="7i")
        repo.save_metrics(db, prior.id, [
            Metric(prior.id, "hip_sway_in", "impact", v, "in", "shoulder_ratio"),
        ])

    # Target swing with two metrics and a linked shot.
    sw = repo.add_swing(db, sid, pid, "golf swing.MOV", club="7i",
                        view_layout="face_on", fps=30.0, width=1080, height=1920)
    repo.save_metrics(db, sw.id, [
        Metric(sw.id, "hip_sway_in", "impact", 2.6, "in", "shoulder_ratio_0.24"),
        Metric(sw.id, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
    ])
    shot = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:00+00:00",
                                   player_id=pid, session_id=sid, ball_speed=119.0,
                                   carry=172.0, club_speed=88.0, club_path=2.4,
                                   face_to_target=-1.2, hla=-3.0,
                                   raw_json=json.dumps({"DeviceID": "R50"})))
    repo.link_shot_to_swing(db, shot.id, sw.id)

    return {"player_id": pid, "session_id": sid, "swing_id": sw.id,
            "shot_id": shot.id}
