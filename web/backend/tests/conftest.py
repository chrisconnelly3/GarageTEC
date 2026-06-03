import json

import pytest
from fastapi.testclient import TestClient

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Media, Coaching
from web.backend.app import create_app
from web.backend import deps


@pytest.fixture
def conn():
    c = dbmod.connect(":memory:")
    dbmod.init_db(conn=c)
    yield c
    c.close()


@pytest.fixture
def client(conn, tmp_path):
    app = create_app()
    app.dependency_overrides[deps.get_conn] = lambda: conn
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    app.dependency_overrides[deps.media_root] = lambda: media_dir
    with TestClient(app) as c:
        c.media_dir = media_dir  # expose for media tests
        yield c


# ---- shared seed helpers ------------------------------------------------

def seed_player(conn, name="Chris", height_in=72.0, handedness="R"):
    return repo.get_or_create_player(conn, name, height_in, handedness)


def seed_ready_swing(conn, player, *, club="7i"):
    """A fully processed swing: metrics + moments + media + coaching + a
    linked shot. Returns the swing."""
    sid = repo.create_session(conn, player.id, location="bay").id
    swing = repo.add_swing(conn, sid, player.id, "swings/1/source.mp4",
                           view_layout="face_on", fps=240.0, width=1920,
                           height=1080, club=club)
    shot = repo.save_shot(conn, Shot(captured_at=dbmod.now_iso(),
                                     player_id=player.id, session_id=sid,
                                     ball_speed=148.2, carry=172.0, vla=13.8))
    repo.link_shot_to_swing(conn, shot.id, swing.id)
    repo.save_moments(conn, swing.id, [
        Moment(swing.id, "address", "face_on", 0, 0.0),
        Moment(swing.id, "impact", "face_on", 120, 0.5),
    ])
    repo.save_metrics(conn, swing.id, [
        Metric(swing.id, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
        Metric(swing.id, "hip_sway_in", "impact", 2.5, "in", "ratio"),
    ])
    repo.save_media(conn, Media(swing.id, "annotated_video",
                                "swings/1/annotated.mp4"))
    repo.save_coaching(conn, Coaching(
        swing_id=swing.id, session_id=None, kind="swing",
        content_json=json.dumps({"headline": "Solid contact",
                                 "findings": ["good tilt"],
                                 "drills": ["towel drill"]}),
        model="claude"))
    return swing
