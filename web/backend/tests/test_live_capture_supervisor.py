"""LiveCaptureSupervisor: rolling-buffer capture thread + auto-trigger core.

No hardware, no real pose: a FakeSource feeds synthetic frames and process_video
is stubbed so the trigger path is tested in isolation.
"""
import sqlite3

import numpy as np
import pytest

from store import db as dbmod
from web.backend.capture import CaptureEventBus
from web.backend.live_capture import LiveCaptureSupervisor


class FakeSource:
    def __init__(self, width=64, height=48):
        self.width = width
        self.height = height
        self.closed = False
        self._i = 0

    def read_composite(self):
        self._i += 1
        return np.full((self.height, self.width, 3), self._i % 256, np.uint8)

    def close(self):
        self.closed = True


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:", check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=c)
    yield c
    c.close()


def _sup(conn, **kw):
    bus = CaptureEventBus()
    sup = LiveCaptureSupervisor(conn=conn, bus=bus,
                                source_factory=lambda: FakeSource(), **kw)
    return sup, bus


# ---- status / lifecycle --------------------------------------------------

def test_status_idle_when_not_started(conn):
    sup, _ = _sup(conn)
    st = sup.status()
    assert st["running"] is False
    assert st["source"] == "none"
    assert st["buffered_frames"] == 0


def test_start_then_buffer_fills_and_stop_closes_source(conn):
    sup, bus = _sup(conn, fps=30.0, window_s=2.0)
    sup.start()
    import time
    deadline = time.time() + 2.0
    while time.time() < deadline and len(sup._buffer) == 0:
        time.sleep(0.01)
    assert sup.status()["running"] is True
    assert len(sup._buffer) > 0
    src = sup._source
    sup.stop()
    assert sup.status()["running"] is False
    assert src.closed is True


def test_start_publishes_status_event(conn):
    sup, bus = _sup(conn)
    sup.start()
    sup.stop()
    events = [e["event"] for e in bus.drain()]
    assert "live_capture_status" in events


# ---- testable trigger core ----------------------------------------------

def test_capture_now_flushes_runs_pipeline_and_emits(conn, monkeypatch):
    sup, bus = _sup(conn, fps=20.0, window_s=2.0)
    # seed the buffer directly (no thread)
    for i in range(10):
        sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=i / 20.0)

    calls = {}

    def fake_process_video(conn_arg, video_path, *, player_id, session_id,
                           on_swing=None, **kw):
        calls["video_path"] = video_path
        calls["player_id"] = player_id
        calls["session_id"] = session_id
        import os
        calls["exists_during"] = os.path.exists(video_path)

        class R:
            swing_id = 4242
        if on_swing is not None:
            on_swing(R())
        return [R()]

    monkeypatch.setattr("web.backend.live_capture.process_video",
                        fake_process_video)

    result = sup.capture_now(player_id=7, session_id=3, shot_id=99)

    assert calls["player_id"] == 7
    assert calls["session_id"] == 3
    assert calls["video_path"].endswith(".mp4")
    assert calls["exists_during"] is True
    # temp file cleaned up afterwards
    import os
    assert not os.path.exists(calls["video_path"])
    # event emitted with the swing id
    captured = [e for e in bus.drain() if e["event"] == "live_swing_captured"]
    assert captured and captured[0]["data"]["swing_id"] == 4242
    assert captured[0]["data"]["shot_id"] == 99
    assert result == [4242]


def test_capture_now_noop_when_buffer_empty(conn, monkeypatch):
    sup, bus = _sup(conn)
    called = {"n": 0}
    monkeypatch.setattr("web.backend.live_capture.process_video",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    out = sup.capture_now(player_id=1, session_id=1, shot_id=1)
    assert out == []
    assert called["n"] == 0


def test_capture_now_swallows_pipeline_errors(conn, monkeypatch):
    sup, bus = _sup(conn)
    sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=0.0)

    def boom(*a, **k):
        raise RuntimeError("pose blew up")

    monkeypatch.setattr("web.backend.live_capture.process_video", boom)
    out = sup.capture_now(player_id=1, session_id=1, shot_id=1)
    assert out == []  # error swallowed; capture never crashes the app
    # an error status is surfaced
    assert any(e["event"] == "live_capture_status" and
               e["data"].get("last_error") for e in bus.drain())


# ---- coaching is key-gated and never breaks capture ---------------------

def test_capture_now_skips_coaching_when_no_api_key(conn, monkeypatch):
    """With ANTHROPIC_API_KEY unset, capture must still succeed: the swing is
    persisted/emitted and NO coaching is attempted (the seed mock stands in)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    sup, bus = _sup(conn, fps=20.0, window_s=2.0)
    for i in range(5):
        sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=i / 20.0)

    coach_calls = {"n": 0}
    monkeypatch.setattr(sup, "_coach_swing",
                        lambda *a, **k: coach_calls.__setitem__("n",
                                                                coach_calls["n"] + 1))

    def fake_process_video(conn_arg, video_path, *, player_id, session_id,
                           on_swing=None, **kw):
        class R:
            swing_id = 77
        if on_swing:
            on_swing(R())
        return [R()]

    monkeypatch.setattr("web.backend.live_capture.process_video",
                        fake_process_video)

    result = sup.capture_now(player_id=1, session_id=1, shot_id=1)
    assert result == [77]                       # swing persisted/emitted
    assert coach_calls["n"] == 0                # coaching skipped (no key)
    captured = [e for e in bus.drain() if e["event"] == "live_swing_captured"]
    assert captured and captured[0]["data"]["swing_id"] == 77


def test_capture_now_coaching_failure_never_breaks_capture(conn, monkeypatch):
    """Even WITH a key, a coaching error must be swallowed: capture still
    persists/emits the swing (coaching is purely additive)."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    sup, bus = _sup(conn, fps=20.0, window_s=2.0)
    for i in range(5):
        sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=i / 20.0)

    def boom_coach(*a, **k):
        raise RuntimeError("api down")
    # Patch the underlying coach_swing so _coach_swing's try/except is exercised.
    monkeypatch.setattr("coach.coach.coach_swing", boom_coach)

    def fake_process_video(conn_arg, video_path, *, player_id, session_id,
                           on_swing=None, **kw):
        class R:
            swing_id = 88
        if on_swing:
            on_swing(R())
        return [R()]

    monkeypatch.setattr("web.backend.live_capture.process_video",
                        fake_process_video)

    result = sup.capture_now(player_id=1, session_id=1, shot_id=1)
    assert result == [88]                       # swing still persisted/emitted
    captured = [e for e in bus.drain() if e["event"] == "live_swing_captured"]
    assert captured and captured[0]["data"]["swing_id"] == 88


# ---- auto-trigger from a shot -------------------------------------------

def test_on_shot_triggers_capture_with_delay_zero(conn, monkeypatch):
    sup, bus = _sup(conn, post_shot_delay_s=0.0)
    sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=0.0)
    seen = {}

    def fake_process_video(conn_arg, video_path, *, player_id, session_id,
                           on_swing=None, **kw):
        seen["player_id"] = player_id
        seen["session_id"] = session_id

        class R:
            swing_id = 1
        if on_swing:
            on_swing(R())
        return [R()]

    monkeypatch.setattr("web.backend.live_capture.process_video",
                        fake_process_video)
    sup.on_shot(player_id=5, session_id=2, shot_id=11)
    # on_shot schedules on a thread; wait for it
    import time
    deadline = time.time() + 2.0
    while time.time() < deadline and "player_id" not in seen:
        time.sleep(0.01)
    assert seen.get("player_id") == 5 and seen.get("session_id") == 2


def test_on_shot_noop_when_not_started_and_no_buffer(conn, monkeypatch):
    sup, bus = _sup(conn, post_shot_delay_s=0.0)
    called = {"n": 0}
    monkeypatch.setattr("web.backend.live_capture.process_video",
                        lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    sup.on_shot(player_id=1, session_id=1, shot_id=1)
    import time
    time.sleep(0.1)
    assert called["n"] == 0  # nothing buffered -> no pipeline run


# ---- Fix 1: capture_now opens its OWN connection per call ----------------

def test_capture_now_uses_fresh_connection_per_call_not_self_conn(
        tmp_path, monkeypatch):
    """capture_now must open a NEW db connection (via db_path) rather than
    reusing self.conn.  This ensures daemon threads never hit SQLite's
    'objects created in a thread can only be used in that same thread' error
    even when self.conn was created without check_same_thread=False.

    Verified by: creating self.conn with check_same_thread=True (the default)
    on the main thread, then running capture_now on a background thread and
    asserting it succeeds (no ProgrammingError) by checking the fake
    process_video was called with a DIFFERENT connection object.
    """
    import threading
    import sqlite3
    from store import db as dbmod

    # Set up a real on-disk db so fresh connections work.
    db_file = str(tmp_path / "test.db")
    # Self.conn with check_same_thread=True (default — would crash on bg thread)
    main_conn = sqlite3.connect(db_file, check_same_thread=True)
    main_conn.row_factory = sqlite3.Row
    main_conn.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=main_conn)

    bus = CaptureEventBus()
    sup = LiveCaptureSupervisor(conn=main_conn, bus=bus,
                                source_factory=lambda: FakeSource(),
                                db_path=db_file,
                                post_shot_delay_s=0.0)

    # Seed the buffer.
    for i in range(5):
        sup._buffer.push(np.zeros((48, 64, 3), np.uint8), time_s=i / 20.0)

    recorded = {}

    def fake_process_video(conn_arg, video_path, *, player_id, session_id,
                           on_swing=None, **kw):
        recorded["conn_id"] = id(conn_arg)
        recorded["main_conn_id"] = id(main_conn)

        class R:
            swing_id = 9999
        if on_swing:
            on_swing(R())
        return [R()]

    monkeypatch.setattr("web.backend.live_capture.process_video",
                        fake_process_video)

    error_holder = []

    def bg():
        try:
            sup.capture_now(player_id=1, session_id=1, shot_id=1)
        except Exception as exc:
            error_holder.append(exc)

    t = threading.Thread(target=bg)
    t.start()
    t.join(timeout=5.0)
    assert not t.is_alive(), "background thread timed out"
    assert not error_holder, f"capture_now raised on bg thread: {error_holder}"
    # The connection passed to process_video must NOT be self.conn.
    assert recorded.get("conn_id") != recorded.get("main_conn_id"), (
        "capture_now must use a fresh per-call connection, not self.conn")
