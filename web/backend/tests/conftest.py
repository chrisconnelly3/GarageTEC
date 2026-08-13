import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Media, Coaching
from web.backend.app import create_app
from web.backend import deps
from web.backend.capture import CaptureEventBus, CaptureSupervisor


class FakeEnrichClient:
    """No-socket stand-in for OpenFlightEnrichClient used across web tests."""
    def __init__(self, host, **kwargs):
        self.host = host
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_connected(self):
        return False


class FakeListener:
    """No-socket stand-in for OpenConnectListener used across web tests."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.alive = False
        self.hand = kwargs.get("handedness")
        self.club = kwargs.get("club")
        # Every club pushed mid-connection, in order. Without this method the
        # supervisor's push would raise AttributeError into its best-effort
        # except and the push path would silently go untested.
        self.pushed_clubs = []

    def start(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def set_handedness(self, h):
        self.hand = h

    def send_player_update(self, *, club=None, handedness=None):
        if club is not None:
            self.club = club
            self.pushed_clubs.append(club)
        if handedness is not None:
            self.hand = handedness


@pytest.fixture
def conn():
    # TestClient runs sync endpoints in a worker thread, so the shared
    # in-memory connection must allow cross-thread use.
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=c)
    yield c
    c.close()


@pytest.fixture
def bus():
    return CaptureEventBus()


@pytest.fixture
def supervisor(conn, bus, tmp_path):
    sup = CaptureSupervisor(
        conn=conn, bus=bus,
        listener_factory=lambda **kw: FakeListener(**kw),
        # Never let a test dial a real OpenFlight host: an OpenFlight-device
        # message would otherwise start a live, reconnecting Socket.IO client.
        enrich_client_factory=lambda host, **kw: FakeEnrichClient(host, **kw),
        buffer_path=str(tmp_path / "pending_shots.jsonl"),
        restart_poll_s=0.02)
    yield sup
    sup.stop()


@pytest.fixture
def client(conn, supervisor, bus, tmp_path):
    app = create_app()
    app.dependency_overrides[deps.get_conn] = lambda: conn
    app.dependency_overrides[deps.get_supervisor] = lambda: supervisor
    app.dependency_overrides[deps.capture_bus] = lambda: bus
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    app.dependency_overrides[deps.media_root] = lambda: media_dir
    with TestClient(app) as c:
        c.media_dir = media_dir  # expose for media tests
        c.supervisor = supervisor
        c.bus = bus
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
