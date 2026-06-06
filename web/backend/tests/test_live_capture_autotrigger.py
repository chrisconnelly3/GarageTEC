"""Auto-trigger: a persisted R50 shot signals the LiveCaptureSupervisor.

CaptureSupervisor holds an optional live_capture reference and, after a shot is
persisted+synced+emitted, calls live.on_shot(player_id, session_id, shot_id).
Verified with a recording stub so no camera/pipeline is touched.
"""
import sqlite3

import pytest

from store import db as dbmod
from web.backend.capture import CaptureEventBus, CaptureSupervisor


SHOT_MSG = {
    "DeviceID": "R50", "ShotNumber": 1,
    "BallData": {"Speed": 148.0, "VLA": 13.0, "CarryDistance": 172.0},
    "ShotDataOptions": {"IsHeartBeat": False},
}


class RecordingLive:
    def __init__(self):
        self.calls = []

    def on_shot(self, *, player_id, session_id, shot_id=None):
        self.calls.append({"player_id": player_id, "session_id": session_id,
                           "shot_id": shot_id})


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=c)
    yield c
    c.close()


def _sup(conn, tmp_path, live=None):
    bus = CaptureEventBus()
    return CaptureSupervisor(
        conn=conn, bus=bus, listener_factory=lambda **_: None,
        buffer_path=str(tmp_path / "p.jsonl"), live_capture=live), bus


def test_shot_triggers_live_capture_on_shot(conn, tmp_path):
    live = RecordingLive()
    sup, _ = _sup(conn, tmp_path, live=live)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    saved = sup.handle_message(SHOT_MSG, source="t")
    assert saved is not None
    assert len(live.calls) == 1
    call = live.calls[0]
    assert call["player_id"] == saved.player_id
    assert call["session_id"] == saved.session_id
    assert call["shot_id"] == saved.id


def test_no_live_capture_reference_is_safe(conn, tmp_path):
    sup, _ = _sup(conn, tmp_path, live=None)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    saved = sup.handle_message(SHOT_MSG, source="t")  # must not raise
    assert saved is not None


def test_live_capture_error_never_blocks_capture(conn, tmp_path):
    class Boom:
        def on_shot(self, **kw):
            raise RuntimeError("live capture exploded")
    sup, _ = _sup(conn, tmp_path, live=Boom())
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    saved = sup.handle_message(SHOT_MSG, source="t")
    assert saved is not None  # capture still succeeds


def test_paused_shot_does_not_trigger_live_capture(conn, tmp_path):
    live = RecordingLive()
    sup, _ = _sup(conn, tmp_path, live=live)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    sup.pause()
    sup.handle_message(SHOT_MSG, source="t")
    assert live.calls == []
