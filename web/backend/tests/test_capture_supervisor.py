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
    sup.start_session()

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
    sup.start_session()
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
    sup.start_session()
    sup.pause()
    sup.handle_message(SHOT_MSG, source="t")
    sup.resume()
    sup.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_heartbeat_is_ignored_even_when_running(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    out = sup.handle_message(HEARTBEAT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert [e for e in bus.drain() if e["event"] == "shot_received"] == []


def test_shot_with_no_active_player_is_dropped_not_orphaned(conn, tmp_path):
    """Shots arriving before a player is selected must NOT persist an
    unattributable orphan (Fix 2: player_id=None rows are invisible and
    uncorrectable; drop them cleanly with a status event)."""
    sup, bus = make_supervisor(conn, tmp_path)
    # Force the supervisor into a recording state without an active player so we
    # exercise the no-player drop path (not the no-session gate). Normally
    # start_session() requires a player; this directly flips the recording flag.
    sup._recording = True
    sup._active_session_id = 1
    out = sup.handle_message(SHOT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert sup.persister.pending_count() == 0   # NOT buffered to disk
    # a status event must announce the drop
    events = bus.drain()
    dropped = [e for e in events
               if e["event"] == "capture_status"
               and e["data"].get("status") == "shot_dropped_no_player"]
    assert dropped, "expected shot_dropped_no_player status event"


def test_set_active_player_attributes_to_that_player_and_emits(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    a = sup.set_active_player("Ann", 65.0, "L")
    b = sup.set_active_player("Bob", 73.0, "R")
    sup.start_session()
    saved = sup.handle_message(SHOT_MSG, source="t")
    assert saved.player_id == b.id and saved.player_id != a.id
    assert any(e["event"] == "active_player_changed" for e in bus.drain())


def test_two_shots_same_player_share_one_session(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
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
    # new session-gate fields: recording is OFF until start_session()
    assert st.session_active is False
    assert st.active_session_id is None


# ---- Start/End Session recording gate -------------------------------------

def test_start_session_with_no_active_player_errors(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)  # nobody selected
    with pytest.raises(ValueError):
        sup.start_session()
    # recording must remain off; no session created
    assert sup.status().session_active is False
    assert sup.status().active_session_id is None
    assert conn.execute("SELECT COUNT(*) c FROM session").fetchone()["c"] == 0


def test_start_session_opens_session_and_turns_recording_on(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    player = sup.set_active_player("Chris", 72.0, "R")
    st = sup.start_session()
    assert st.session_active is True
    assert st.active_session_id is not None
    # a real session row exists for this player
    row = conn.execute("SELECT player_id, ended_at FROM session WHERE id=?",
                       (st.active_session_id,)).fetchone()
    assert row["player_id"] == player.id
    assert row["ended_at"] is None  # still open


def test_shot_while_recording_persists_to_started_session(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    st = sup.start_session()
    saved = sup.handle_message(SHOT_MSG, source="t")
    assert saved is not None
    # the shot attaches to the explicitly-started session, not an arbitrary one
    assert saved.session_id == st.active_session_id
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_shot_while_not_recording_is_dropped_with_no_session_event(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")  # player set, but NO session
    out = sup.handle_message(SHOT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    assert sup.persister.pending_count() == 0   # NOT buffered
    assert sup.status().session_active is False
    dropped = [e for e in bus.drain()
               if e["event"] == "capture_status"
               and e["data"].get("status") == "shot_dropped_no_session"]
    assert dropped, "expected shot_dropped_no_session status event"


def test_end_session_turns_recording_off_and_ends_session(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    st = sup.start_session()
    sid = st.active_session_id
    end_st = sup.end_session()
    assert end_st.session_active is False
    assert end_st.active_session_id is None
    # the session is now closed in the store
    row = conn.execute("SELECT ended_at FROM session WHERE id=?", (sid,)).fetchone()
    assert row["ended_at"] is not None
    # subsequent shots are dropped (recording is off)
    out = sup.handle_message(SHOT_MSG, source="t")
    assert out is None
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_end_session_when_none_active_is_safe(conn, tmp_path):
    sup, _ = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    st = sup.end_session()  # nothing to end
    assert st.session_active is False
    assert st.active_session_id is None


def test_start_session_emits_status_event(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    statuses = [e["data"].get("status") for e in bus.drain()
                if e["event"] == "capture_status"]
    assert "session_started" in statuses


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


def test_active_club_tags_shots_and_status(conn, tmp_path):
    sup, bus = make_supervisor(conn, tmp_path)
    sup.set_active_player("Chris", 72.0, "R")
    sup.start_session()
    sup.set_active_club("7 Iron")
    assert sup.status().active_club == "7 Iron"
    saved = sup.handle_message(SHOT_MSG, source="test")
    assert saved.club == "7 Iron"                    # shot tagged with the club
    row = conn.execute("SELECT club FROM shot WHERE id=?", (saved.id,)).fetchone()
    assert row["club"] == "7 Iron"                   # persisted
    assert "active_club_changed" in [e["event"] for e in bus.drain()]


def test_respawned_listener_carries_the_current_club(supervisor):
    """Regression: a club selected before the monitor connects must survive a respawn."""
    supervisor.set_active_club("7 Iron")
    supervisor._spawn_listener()
    assert supervisor._listener.kwargs["club"] == "I7"


# ---- Fix 3: restart() must not double-spawn under supervise race ----------

def test_restart_does_not_double_spawn_under_supervise_race(conn, tmp_path):
    """restart() sets _restarting while it works; _supervise must skip
    re-spawn while that flag is set, so we never bind port 921 twice."""
    import time
    made = []
    sup = CaptureSupervisor(
        conn=conn, bus=CaptureEventBus(),
        listener_factory=lambda **kw: made.append(FakeListener(**kw)) or made[-1],
        buffer_path=str(tmp_path / "p.jsonl"),
        restart_poll_s=0.005)   # very fast supervise loop
    sup.start()
    assert _wait(lambda: len(made) == 1 and made[0].alive)

    # Simulate the listener dying while restart() is executing:
    # hold _restarting=True manually and check _supervise doesn't spawn.
    with sup._lock:
        sup._restarting = True
    made[0].die()
    time.sleep(0.05)  # let supervise loop run several times
    count_while_restarting = len(made)
    with sup._lock:
        sup._restarting = False

    # The supervise loop must NOT have spawned while restarting was set.
    assert count_while_restarting == 1, (
        f"expected no extra spawn while _restarting=True, got {count_while_restarting}")

    # After flag cleared, a dead listener SHOULD be restarted normally.
    assert _wait(lambda: len(made) == 2 and made[1].alive)
    sup.stop()
