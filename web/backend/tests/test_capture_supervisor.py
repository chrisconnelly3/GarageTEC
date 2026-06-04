import sqlite3

import pytest

from store import db as dbmod
from web.backend.capture import CaptureEventBus, CaptureSupervisor


SHOT_MSG = {
    "DeviceID": "R50", "ShotNumber": 1,
    "BallData": {"Speed": 148.0, "VLA": 13.0, "TotalSpin": 2700.0,
                 "CarryDistance": 172.0},
    "ShotDataOptions": {"IsHeartBeat": False},
}
HEARTBEAT_MSG = {"ShotDataOptions": {"IsHeartBeat": True}}


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=c)
    yield c
    c.close()


def make_supervisor(conn, tmp_path, **kw):
    bus = CaptureEventBus()
    sup = CaptureSupervisor(
        conn=conn, bus=bus,
        listener_factory=lambda **_: None,  # core tests never start a listener
        buffer_path=str(tmp_path / "pending.jsonl"),
        **kw)
    return sup, bus


def test_running_shot_persists_attributes_syncs_and_emits(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")

    saved = sup.handle_message(SHOT_MSG, source="test")

    assert saved is not None
    assert saved.player_id == sup.session_mgr.active_player.id
    assert saved.session_id is not None
    assert saved.ball_speed == 148.0
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1
    assert sup.status().shot_count == 1
    events = [e["event"] for e in bus.drain()]
    assert "shot_received" in events


def test_paused_discards_shot_no_persist_no_emit(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.pause()

    out = sup.handle_message(SHOT_MSG, source="test")

    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert sup.status().shot_count == 0
    # paused must NOT buffer either (discard, not defer)
    assert sup.persister.pending_count() == 0
    assert [e for e in bus.drain() if e["event"] == "shot_received"] == []


def test_resume_after_pause_persists_again(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.pause()
    sup.handle_message(SHOT_MSG, source="t")
    sup.resume()
    sup.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_heartbeat_is_ignored_even_when_running(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    out = sup.handle_message(HEARTBEAT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert [e for e in bus.drain() if e["event"] == "shot_received"] == []


def test_shot_with_no_active_player_is_buffered_not_lost(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)  # nobody selected yet
    out = sup.handle_message(SHOT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert sup.persister.pending_count() == 1  # buffered, not discarded


def test_set_active_player_attributes_to_that_player_and_emits(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    a = sup.set_active_player("Ann", 65.0, "L")
    b = sup.set_active_player("Bob", 73.0, "R")
    saved = sup.handle_message(SHOT_MSG, source="t")
    assert saved.player_id == b.id and saved.player_id != a.id
    assert any(e["event"] == "active_player_changed" for e in bus.drain())


def test_two_shots_same_player_share_one_session(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    s1 = sup.handle_message(SHOT_MSG, source="t")
    s2 = sup.handle_message(SHOT_MSG, source="t")
    assert s1.session_id == s2.session_id


def test_status_snapshot_shape(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    st = sup.status()
    assert st.status == "stopped"
    assert st.paused is False
    assert st.shot_count == 0
    assert st.active_player_id is None


def test_set_handedness_propagates_to_listener_on_player_switch(conn, tmp_path):
    # the listener factory hands back a stub recording set_handedness calls
    class StubListener:
        def __init__(self): self.hand = None
        def start(self): pass
        def stop(self): pass
        def set_handedness(self, h): self.hand = h
    stub = StubListener()
    bus = CaptureEventBus()
    sup = CaptureSupervisor(conn=conn, bus=bus,
                            listener_factory=lambda **_: stub,
                            buffer_path=str(tmp_path / "p.jsonl"))
    sup.start()
    sup.set_active_player("Lefty", 70.0, "L")
    assert stub.hand == "LH"
    sup.set_active_player("Righty", 70.0, "R")
    assert stub.hand == "RH"
    sup.stop()


class FakeListener:
    """Stands in for OpenConnectListener with NO socket. `alive` models the
    listener thread being up; `die()` simulates an unexpected thread death."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.alive = False
        self.start_calls = 0
        self.stop_calls = 0
        self.hand = kwargs.get("handedness")

    def start(self):
        self.alive = True
        self.start_calls += 1

    def stop(self):
        self.alive = False
        self.stop_calls += 1

    def set_handedness(self, h):
        self.hand = h

    # test helper, not part of the real interface
    def die(self):
        self.alive = False


def _wait(predicate, timeout=2.0):
    import time
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_start_creates_and_starts_listener(conn, tmp_path):
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"), restart_poll_s=0.02)
    sup.start()
    assert made and made[0].alive is True
    assert made[0].kwargs["on_message"] == sup.handle_message
    sup.stop()
    assert made[0].alive is False and sup.status().status == "stopped"


def test_start_is_idempotent(conn, tmp_path):
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"), restart_poll_s=0.02)
    sup.start()
    sup.start()  # second start must not spawn a second listener
    assert len(made) == 1
    sup.stop()


def test_auto_restart_when_listener_thread_dies(conn, tmp_path):
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"), restart_poll_s=0.02)
    sup.start()
    assert _wait(lambda: len(made) == 1 and made[0].alive)
    made[0].die()  # simulate unexpected death
    # supervising loop notices and spawns a fresh listener
    assert _wait(lambda: len(made) == 2 and made[1].alive)
    sup.stop()
    assert made[-1].alive is False


def test_stop_halts_auto_restart(conn, tmp_path):
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"), restart_poll_s=0.02)
    sup.start()
    assert _wait(lambda: len(made) == 1)
    sup.stop()
    made[0].die()
    import time
    time.sleep(0.1)  # give the loop a chance to (wrongly) restart
    assert len(made) == 1  # stopped: no restart


def test_restart_replaces_listener(conn, tmp_path):
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"), restart_poll_s=0.02)
    sup.start()
    sup.restart()
    assert _wait(lambda: len(made) == 2 and made[1].alive)
    assert made[0].stop_calls == 1
    sup.stop()
