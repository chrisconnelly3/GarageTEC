# Unified App Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fold the R50 capture engine into the FastAPI dashboard so a single touch-first app captures, reviews, and coaches — auto-starting the GSPro Open Connect listener in a background thread with Pause/Resume, capture REST + SSE, a sidebar-nav frontend with a persistent global bar, and a kiosk launcher — while retiring the standalone Tkinter shell.

**Architecture:** A new `web/backend/capture.py` holds a `CaptureSupervisor` whose core message handling is the directly-callable `handle_message(obj, source)` method (running vs paused vs heartbeat; player/session attribution via `catcher.sessionmgr`; persist via `catcher.persist`; `sync.SyncService.on_new_shot`; capture-event emit). The actual `OpenConnectListener` thread is a thin, injectable wrapper (a listener *factory* is passed in) so tests inject a fake and never bind port 921 or need an R50. The FastAPI `lifespan` starts/stops a module-level singleton supervisor exposed through `deps.py`; `api_capture.py` exposes status/pause/resume/restart/active-player; `events.py` gains an in-process capture-event bus pushed onto the existing `/events` SSE stream. The React frontend adds a global bar + left sidebar, reworks Live to the spec's hierarchy, and adds a Connect screen, all wired to `/api/capture/*` + SSE.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, httpx (TestClient), pytest, stdlib `sqlite3` + `threading` (existing `store/`, `catcher/`, `sync/`); React 18 + Vite 5, vitest + @testing-library/react.

Spec: `docs/superpowers/specs/2026-06-03-unified-app-merge-design.md`
Reuses (unchanged): `catcher/openconnect.py` (`OpenConnectListener`), `catcher/shotmap.py` (`map_message`, `is_heartbeat`), `catcher/sessionmgr.py` (`SessionManager`), `catcher/persist.py` (`ShotPersister`), `sync/service.py` (`SyncService.on_new_shot`), `store/db.py`, `store/repo.py`.

Python (full path; `py` launcher NOT on PATH): `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`
Node/npm: `C:\Program Files\nodejs` (on PATH as `npm`).

### Real engine interfaces this plan calls (verified verbatim)

- `OpenConnectListener(port=921, on_message=Callable[[dict, str], None], *, handedness="RH", probe_ip=None, on_status=Callable[[str, str], None])` — `.start()` spawns a daemon `_server_loop` thread (binds `0.0.0.0:port`); `.stop()`; `.set_handedness(str)`. `on_status(kind, detail)` kinds: `"listening"`, `"connected"`, `"disconnected"`, `"bind_error"`. The thread calls `on_message(obj, source)` per parsed JSON object. **We never construct a real one in tests — a factory seam injects a fake.**
- `shotmap.map_message(obj) -> Shot | None` (None for heartbeats; leaves `player_id`/`session_id` None); `shotmap.is_heartbeat(obj) -> bool`.
- `SessionManager(conn, idle_minutes=15)`: `.set_active_player(name, height_in, handedness) -> Player` (sets `.active_player`), `.active_player`, `.attribute(conn, shot) -> Shot` (raises `RuntimeError` if no active player; stamps `player_id`/`session_id`/`captured_at`), `.roster(conn=None)`, `.sweep_idle(conn) -> int`.
- `ShotPersister(buffer_path=None)`: `.save(conn, shot) -> Shot | None` (None when buffered on failure; never raises for DB errors), `._buffer(shot)`, `.pending_count() -> int`, `.replay(conn) -> int`.
- `SyncService(conn).on_new_shot(*, shot_id) -> MatchProposal | None`.
- `store.repo.save_shot(conn, shot)` sets `shot.id`; `store.db.connect(path=None)` → WAL connection (we pass `check_same_thread=False` for the listener thread per conftest precedent).

---

## File Structure

### Backend — new

- `web/backend/capture.py` — `CaptureSupervisor` (testable core `handle_message` + thread lifecycle via an injected listener factory) + `CaptureStatus` snapshot dataclass + `CaptureEventBus`.
- `web/backend/api_capture.py` — `GET /api/capture/status`, `POST /api/capture/pause`, `POST /api/capture/resume`, `POST /api/capture/restart`, `POST /api/capture/active-player`.
- `web/backend/tests/test_capture_supervisor.py` — supervisor core + lifecycle, fake-feed driven, NO sockets.
- `web/backend/tests/test_api_capture.py` — capture API via TestClient (supervisor overridden with a fake).
- `web/backend/tests/test_capture_events.py` — capture events on the SSE stream.

### Backend — edited

- `web/backend/deps.py` — add a `get_supervisor()` singleton seam + `capture_bus()` seam (overridable in tests, exactly like `get_conn`/`media_root`).
- `web/backend/events.py` — add a process-local `CaptureEventBus` consumed by `/events` (alongside the existing `SwingWatcher`), emitting `shot_received`, `capture_status`, `active_player_changed` SSE frames.
- `web/backend/app.py` — add a FastAPI `lifespan` that `supervisor.start()` on startup and `supervisor.stop()` on shutdown; include `api_capture.router`.
- `web/backend/tests/conftest.py` — add a `fake_listener_factory` fixture + a `supervisor` fixture wired to the in-memory `conn`; override `deps.get_supervisor`/`deps.capture_bus` in the `client` fixture so the auto-start lifespan uses a fake listener (never binds 921).

### Frontend — new (`web/frontend/src`)

- `src/components/GlobalBar.jsx` — persistent player switch + R50 status chip + Pause/Resume, wired to `/api/capture/*` + SSE.
- `src/components/Sidebar.jsx` — left nav (Live, Review, History, Sessions, Players, Sync, Connect).
- `src/pages/Connect.jsx` — ported catcher connect wizard (R50 → Connect → GSPro steps + reconnect).
- `src/useCapture.js` — hook: capture status + SSE capture events + pause/resume/setActivePlayer actions.
- `src/components/GlobalBar.test.jsx` — one vitest component test.

### Frontend — edited (`web/frontend/src`)

- `src/api.js` — add `getCaptureStatus`, `pauseCapture`, `resumeCapture`, `restartCapture`, `setActivePlayer`.
- `src/useEvents.js` — also expose the latest capture event (status/shot/player) so the global bar + Live update without polling.
- `src/pages/Live.jsx` — rework to the 4.3 hierarchy: replay hero (realtime⇄slow-mo + skeleton toggle), body-metrics, AI read, compact ball/club strip.
- `src/App.jsx` — switch the top `<nav>` for `<Sidebar>` + `<GlobalBar>` layout; add the `/connect` route.

### Launcher / retirement

- `run_garagetec.cmd` (repo root) — starts uvicorn, waits for `/api/health`, opens the browser fullscreen/kiosk.
- DELETE `catcher/app.py`, `catcher/run.py`, `catcher/build_exe.md`, and `catcher/tests/test_app.py` (the only test that imports the retired shell). KEEP `catcher/openconnect.py`, `shotmap.py`, `sessionmgr.py`, `persist.py` and their tests (`test_openconnect.py`, `test_persist.py`, `test_sessionmgr.py`, `test_shotmap.py`).

Conventions: every repo call passes `conn` first. Timestamps are ISO-8601 UTC from `store.db.now_iso()`. The listener thread uses its OWN `sqlite3` connection (`check_same_thread=False`, WAL) — never the request connection. The frontend talks only to same-origin `/api`, `/events`, `/media`.

---

## Task 1: CaptureEventBus — the in-process capture event channel

A tiny thread-safe pub/sub the supervisor pushes capture events onto and the SSE route drains. Pure, no I/O, no sockets — testable directly. Built first so the supervisor and SSE both depend on a tested primitive.

**Files:**
- Create: `web/backend/capture.py` (start it — bus only for now)
- Create: `web/backend/tests/test_capture_bus.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_capture_bus.py`:
```python
from web.backend.capture import CaptureEventBus


def test_publish_then_drain_returns_events_in_order():
    bus = CaptureEventBus()
    bus.publish("capture_status", {"status": "connected"})
    bus.publish("shot_received", {"shot_id": 5, "player_id": 1})
    drained = bus.drain()
    assert [e["event"] for e in drained] == ["capture_status", "shot_received"]
    assert drained[1]["data"] == {"shot_id": 5, "player_id": 1}


def test_drain_is_idempotent_clears_buffer():
    bus = CaptureEventBus()
    bus.publish("capture_status", {"status": "paused"})
    assert len(bus.drain()) == 1
    assert bus.drain() == []  # already consumed


def test_drain_is_thread_safe_under_concurrent_publish():
    import threading
    bus = CaptureEventBus()

    def producer():
        for i in range(100):
            bus.publish("shot_received", {"i": i})

    threads = [threading.Thread(target=producer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # all 400 events must be drainable exactly once, no loss/crash
    assert len(bus.drain()) == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_bus.py -v`
Expected: FAIL (`No module named 'web.backend.capture'`).

- [ ] **Step 3: Write minimal implementation**

`web/backend/capture.py` (initial — the bus only; the supervisor is appended in Task 2):
```python
"""In-process capture engine for the unified app.

CaptureEventBus is a thread-safe buffer of capture events (the listener thread
publishes; the SSE request coroutine drains). CaptureSupervisor (added in the
next task) owns the OpenConnectListener and turns parsed messages into persisted,
synced, broadcast shots.
"""
import threading


class CaptureEventBus:
    """Thread-safe FIFO of capture events. publish() from any thread; drain()
    from the SSE coroutine. Each event is {"event": str, "data": dict}."""

    def __init__(self):
        self._lock = threading.Lock()
        self._events = []

    def publish(self, event: str, data: dict):
        with self._lock:
            self._events.append({"event": event, "data": data})

    def drain(self) -> list:
        with self._lock:
            out = self._events
            self._events = []
            return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_bus.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/capture.py web/backend/tests/test_capture_bus.py
git commit -m "feat(web): CaptureEventBus thread-safe capture event channel"
```

---

## Task 2: CaptureSupervisor core — `handle_message` (running / paused / heartbeat)

The heart of the merge and the most heavily TDD'd piece. `handle_message(obj, source)` is a plain method — **no socket, no thread** — so every behavior is tested by calling it directly with a dict. It reuses the real `shotmap`, `SessionManager`, `ShotPersister`, and `SyncService`. The OpenConnectListener wiring is deferred to Task 3 (a thin wrapper around this method).

**Files:**
- Modify: `web/backend/capture.py` (append `CaptureStatus` + `CaptureSupervisor` with the core only)
- Create: `web/backend/tests/test_capture_supervisor.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_capture_supervisor.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_supervisor.py -v`
Expected: FAIL (`cannot import name 'CaptureSupervisor'`).

- [ ] **Step 3: Write minimal implementation** (append to `web/backend/capture.py`)

```python
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from catcher import shotmap
from catcher.openconnect import OpenConnectListener, PORT_DEFAULT
from catcher.persist import ShotPersister
from catcher.sessionmgr import SessionManager
from sync.service import SyncService


@dataclass
class CaptureStatus:
    status: str                      # stopped|listening|connected|paused
    paused: bool
    connected: bool
    shot_count: int
    active_player_id: Optional[int]
    last_error: Optional[str]


def _default_listener_factory(**kwargs):
    """Real wrapper: build an OpenConnectListener. Injected fakes replace this
    in tests so no socket is ever opened and port 921 is never bound."""
    return OpenConnectListener(**kwargs)


class CaptureSupervisor:
    """Owns the R50 capture engine inside the FastAPI app.

    `handle_message(obj, source)` is the testable core (no socket/thread):
    running -> map+attribute+persist+sync+emit; paused -> discard; heartbeat ->
    ignore. The listener thread (Task 3) is a thin wrapper that just calls
    handle_message. `listener_factory` is injectable so tests pass a fake.
    """

    def __init__(self, *, conn, bus, listener_factory: Callable = _default_listener_factory,
                 port: int = PORT_DEFAULT, idle_minutes: int = 15,
                 probe_ip: Optional[str] = None, buffer_path: Optional[str] = None):
        self.conn = conn
        self.bus = bus
        self._listener_factory = listener_factory
        self.port = port
        self.probe_ip = probe_ip

        self.session_mgr = SessionManager(conn, idle_minutes=idle_minutes)
        self.persister = ShotPersister(buffer_path=buffer_path)
        self.sync = SyncService(conn)

        self._lock = threading.Lock()
        self._paused = False
        self._status = "stopped"
        self._connected = False
        self._shot_count = 0
        self._last_error = None
        self._listener = None

    # ---- core (directly tested, no socket) -------------------------------
    def handle_message(self, obj: dict, source: str = ""):
        shot = shotmap.map_message(obj)
        if shot is None:
            return None  # heartbeat
        if self._paused:
            return None  # discard: keep R50 connected, do NOT persist/analyze
        if self.session_mgr.active_player is None:
            self.persister._buffer(shot)  # no one selected: don't lose it
            return None
        self.session_mgr.attribute(self.conn, shot)
        saved = self.persister.save(self.conn, shot)
        if saved is None:
            return None  # buffered on DB failure; nothing to sync/emit yet
        with self._lock:
            self._shot_count += 1
        try:
            self.sync.on_new_shot(shot_id=saved.id)
        except Exception:
            pass  # matching is best-effort; never block capture
        self.bus.publish("shot_received", {
            "shot_id": saved.id, "player_id": saved.player_id,
            "session_id": saved.session_id, "ball_speed": saved.ball_speed,
            "carry": saved.carry, "shot_count": self._shot_count})
        return saved

    # ---- active player ----------------------------------------------------
    def set_active_player(self, name, height_in, handedness):
        player = self.session_mgr.set_active_player(name, height_in, handedness)
        if self._listener is not None:
            self._listener.set_handedness("LH" if handedness == "L" else "RH")
        self.bus.publish("active_player_changed",
                         {"player_id": player.id, "name": player.name})
        return player

    # ---- status -----------------------------------------------------------
    def status(self) -> CaptureStatus:
        with self._lock:
            ap = self.session_mgr.active_player
            return CaptureStatus(
                status="paused" if self._paused and self._status != "stopped"
                       else self._status,
                paused=self._paused, connected=self._connected,
                shot_count=self._shot_count,
                active_player_id=ap.id if ap else None,
                last_error=self._last_error)

    # ---- pause/resume -----------------------------------------------------
    def pause(self):
        self._paused = True
        self.bus.publish("capture_status", {"status": "paused"})

    def resume(self):
        self._paused = False
        self.bus.publish("capture_status",
                         {"status": "connected" if self._connected else "listening"})

    # ---- start/stop placeholders (fleshed out in Task 3) ------------------
    def start(self):
        if self._listener is None:
            self._listener = self._listener_factory(
                port=self.port, on_message=self.handle_message,
                handedness="RH", probe_ip=self.probe_ip,
                on_status=self._on_status)
        self._status = "listening"

    def stop(self):
        if self._listener is not None:
            self._listener.stop()
        self._listener = None
        self._status = "stopped"
        self._connected = False

    def _on_status(self, kind, detail):
        if kind == "connected":
            self._connected = True
            self._status = "connected"
        elif kind in ("disconnected", "listening"):
            self._connected = (kind == "connected")
            self._status = "listening"
        elif kind == "bind_error":
            self._last_error = detail
        self.bus.publish("capture_status", {"status": self._status,
                                            "detail": detail})
```

> Note: `start()`/`stop()` here are minimal so the handedness test passes; Task 3
> adds the supervising thread + auto-restart and replaces these bodies.

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_supervisor.py -v`
Expected: PASS (all core behaviors).

- [ ] **Step 5: Commit**

```bash
git add web/backend/capture.py web/backend/tests/test_capture_supervisor.py
git commit -m "feat(web): CaptureSupervisor core (running/paused/heartbeat, attribute/persist/sync/emit)"
```

---

## Task 3: Supervisor thread lifecycle + auto-restart-on-death

Wire `start()/stop()/restart()` to a supervising thread that owns the injected listener and **auto-restarts** it if the listener thread dies unexpectedly while running. All tested with a **fake listener** whose "thread" we can kill on command — no socket, no port, no sleeps in the assertion path (a short bounded poll only).

**Files:**
- Modify: `web/backend/capture.py` (replace `start`/`stop`, add `restart` + supervising loop)
- Modify: `web/backend/tests/test_capture_supervisor.py` (add lifecycle tests)

- [ ] **Step 1: Write the failing tests** (append to `test_capture_supervisor.py`)

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_supervisor.py -v`
Expected: FAIL (`CaptureSupervisor.__init__` got unexpected `restart_poll_s`; no `restart`; no auto-restart).

- [ ] **Step 3: Implement the lifecycle** (in `web/backend/capture.py`)

Add `restart_poll_s` to `__init__` and replace the Task-2 `start`/`stop` placeholders:

```python
    # add to __init__ signature: restart_poll_s: float = 1.0
    # and in the body:
    #   self.restart_poll_s = restart_poll_s
    #   self._run = False
    #   self._supervisor_thread = None
```

```python
    def start(self):
        with self._lock:
            if self._run:
                return  # idempotent
            self._run = True
        self._spawn_listener()
        self._status = "listening"
        self._supervisor_thread = threading.Thread(
            target=self._supervise, daemon=True)
        self._supervisor_thread.start()

    def stop(self):
        with self._lock:
            self._run = False
        if self._listener is not None:
            self._listener.stop()
        self._listener = None
        self._status = "stopped"
        self._connected = False

    def restart(self):
        if self._listener is not None:
            self._listener.stop()
        self._spawn_listener()

    def _spawn_listener(self):
        self._listener = self._listener_factory(
            port=self.port, on_message=self.handle_message,
            handedness=self._handedness(), probe_ip=self.probe_ip,
            on_status=self._on_status)
        self._listener.start()

    def _handedness(self):
        ap = self.session_mgr.active_player
        return "LH" if (ap and ap.handedness == "L") else "RH"

    def _listener_alive(self):
        lst = self._listener
        # OpenConnectListener exposes `.running`; the fake exposes `.alive`.
        return bool(getattr(lst, "alive", getattr(lst, "running", False)))

    def _supervise(self):
        import time
        while self._run:
            if self._listener is not None and not self._listener_alive():
                self._last_error = "listener thread died; restarting"
                self.bus.publish("capture_status",
                                 {"status": "restarting"})
                self._spawn_listener()
            time.sleep(self.restart_poll_s)
```

Remove the now-superseded minimal `start`/`stop` bodies from Task 2. Keep
`_on_status` and `set_active_player` as-is (the latter already calls
`set_handedness` when a listener exists).

> Real-vs-fake liveness: `OpenConnectListener` sets `.running=True` in `start()`
> and `False` in `stop()`; `_listener_alive()` reads `.alive` (fake) or
> `.running` (real). Auto-restart triggers only while `self._run` is True.

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_supervisor.py -v`
Expected: PASS (core + lifecycle + auto-restart).

- [ ] **Step 5: Commit**

```bash
git add web/backend/capture.py web/backend/tests/test_capture_supervisor.py
git commit -m "feat(web): supervisor thread lifecycle + auto-restart-on-death (fake-listener tested)"
```

---

## Task 4: deps seams — supervisor singleton + capture bus

Mirror the existing `get_conn`/`media_root` seams so the API routers and SSE depend on overridable providers. The real singleton builds the supervisor against a dedicated listener-thread connection; tests override both.

**Files:**
- Modify: `web/backend/deps.py`
- Create: `web/backend/tests/test_deps_supervisor.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_deps_supervisor.py`:
```python
from web.backend import deps
from web.backend.capture import CaptureSupervisor, CaptureEventBus


def test_capture_bus_is_a_singleton():
    deps.reset_capture_singletons()
    assert deps.capture_bus() is deps.capture_bus()


def test_get_supervisor_is_a_singleton_and_uses_the_shared_bus():
    deps.reset_capture_singletons()
    sup = deps.get_supervisor()
    assert isinstance(sup, CaptureSupervisor)
    assert deps.get_supervisor() is sup
    assert sup.bus is deps.capture_bus()


def test_reset_clears_the_singletons():
    deps.reset_capture_singletons()
    first = deps.get_supervisor()
    deps.reset_capture_singletons()
    assert deps.get_supervisor() is not first
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_deps_supervisor.py -v`
Expected: FAIL (`module 'web.backend.deps' has no attribute 'capture_bus'`).

- [ ] **Step 3: Implement the seams** (append to `web/backend/deps.py`)

```python
import sqlite3

from web.backend.capture import CaptureEventBus, CaptureSupervisor

_capture_bus = None
_supervisor = None


def _listener_conn():
    """A dedicated connection for the listener thread: never the request conn.
    check_same_thread=False so the daemon thread may use it; WAL for the catcher's
    buffer-on-failure persistence to absorb transient locks."""
    conn = sqlite3.connect(dbmod.default_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    dbmod.init_db(conn=conn)
    return conn


def capture_bus() -> CaptureEventBus:
    global _capture_bus
    if _capture_bus is None:
        _capture_bus = CaptureEventBus()
    return _capture_bus


def get_supervisor() -> CaptureSupervisor:
    global _supervisor
    if _supervisor is None:
        _supervisor = CaptureSupervisor(conn=_listener_conn(), bus=capture_bus())
    return _supervisor


def reset_capture_singletons():
    """Test hook: drop the singletons so each test gets a fresh pair."""
    global _capture_bus, _supervisor
    if _supervisor is not None:
        try:
            _supervisor.stop()
        except Exception:
            pass
    _capture_bus = None
    _supervisor = None
```

(Existing `from store import db as dbmod` import at the top of `deps.py` already provides `dbmod`.)

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_deps_supervisor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/deps.py web/backend/tests/test_deps_supervisor.py
git commit -m "feat(web): deps seams for capture supervisor + event bus singletons"
```

---

## Task 5: FastAPI lifespan wiring (auto-start / clean stop)

Start the supervisor on app startup and stop it on shutdown via FastAPI `lifespan`. The test must NOT bind port 921: the `client` fixture overrides `get_supervisor` with a fake-listener-backed supervisor so the auto-start exercises the wiring without a socket.

**Files:**
- Modify: `web/backend/app.py`
- Modify: `web/backend/tests/conftest.py` (add capture fixtures + override in `client`)
- Create: `web/backend/tests/test_lifespan.py`

- [ ] **Step 1: Extend `conftest.py`** (add capture seams; the existing `conn`/`client` fixtures stay)

Append to `web/backend/tests/conftest.py`:
```python
from web.backend.capture import CaptureEventBus, CaptureSupervisor


class FakeListener:
    """No-socket stand-in for OpenConnectListener used across web tests."""
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.alive = False
        self.hand = kwargs.get("handedness")

    def start(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def set_handedness(self, h):
        self.hand = h


@pytest.fixture
def bus():
    return CaptureEventBus()


@pytest.fixture
def supervisor(conn, bus, tmp_path):
    sup = CaptureSupervisor(
        conn=conn, bus=bus,
        listener_factory=lambda **kw: FakeListener(**kw),
        buffer_path=str(tmp_path / "pending_shots.jsonl"),
        restart_poll_s=0.02)
    yield sup
    sup.stop()
```

Then update the `client` fixture so the auto-start lifespan uses the fake-backed supervisor and the shared bus (no socket bound):
```python
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
        c.media_dir = media_dir
        c.supervisor = supervisor
        c.bus = bus
        yield c
```

> The lifespan (Step 3) must read the supervisor through `app.dependency_overrides`
> if present, else `deps.get_supervisor()`. Implement that lookup in `app.py` so
> the override actually takes effect during startup.

- [ ] **Step 2: Write the failing test**

`web/backend/tests/test_lifespan.py`:
```python
def test_supervisor_started_on_app_startup(client):
    # entering the TestClient context ran lifespan startup
    assert client.supervisor.status().status in ("listening", "connected")


def test_supervisor_stopped_on_shutdown(conn, supervisor, bus, tmp_path):
    from fastapi.testclient import TestClient
    from web.backend.app import create_app
    from web.backend import deps

    app = create_app()
    app.dependency_overrides[deps.get_conn] = lambda: conn
    app.dependency_overrides[deps.get_supervisor] = lambda: supervisor
    app.dependency_overrides[deps.capture_bus] = lambda: bus
    media = tmp_path / "m"; media.mkdir()
    app.dependency_overrides[deps.media_root] = lambda: media
    with TestClient(app):
        assert supervisor.status().status != "stopped"
    # context exit ran lifespan shutdown
    assert supervisor.status().status == "stopped"
```

- [ ] **Step 3: Implement the lifespan** (in `web/backend/app.py`)

```python
from contextlib import asynccontextmanager

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, api_capture,
    events, media, deps,
)


def _resolve_supervisor(app):
    override = app.dependency_overrides.get(deps.get_supervisor)
    return override() if override else deps.get_supervisor()


@asynccontextmanager
async def lifespan(app):
    supervisor = _resolve_supervisor(app)
    supervisor.start()
    try:
        yield
    finally:
        supervisor.stop()
```

In `create_app()` pass `lifespan=lifespan` to `FastAPI(...)` and add
`app.include_router(api_capture.router)` after the other routers:
```python
    app = FastAPI(title="GarageTEC Screen", lifespan=lifespan)
    ...
    app.include_router(api_sync.router)
    app.include_router(api_capture.router)
    app.include_router(events.router)
    app.include_router(media.router)
```

> `api_capture` is created in Task 6; to keep this task's suite importable, create
> a stub `web/backend/api_capture.py` now with just `from fastapi import APIRouter;
> router = APIRouter(prefix="/api/capture", tags=["capture"])` and flesh it out in
> Task 6. (Listed in Task 6's files.)

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_lifespan.py -v`
Expected: PASS (startup/shutdown drive the fake supervisor; no port bound).

- [ ] **Step 5: Commit**

```bash
git add web/backend/app.py web/backend/api_capture.py web/backend/tests/conftest.py web/backend/tests/test_lifespan.py
git commit -m "feat(web): FastAPI lifespan auto-starts/stops CaptureSupervisor (fake-listener tested)"
```

---

## Task 6: Capture API — status / pause / resume / restart / active-player

Thin routes over the supervisor, tested via TestClient with the fake-backed supervisor from conftest. Pausing must stop persistence (asserted end-to-end through the API).

**Files:**
- Modify: `web/backend/api_capture.py` (replace the Task-5 stub)
- Create: `web/backend/tests/test_api_capture.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_capture.py`:
```python
SHOT_MSG = {
    "DeviceID": "R50", "ShotNumber": 1,
    "BallData": {"Speed": 148.0, "VLA": 13.0, "CarryDistance": 172.0},
    "ShotDataOptions": {"IsHeartBeat": False},
}


def test_status_returns_supervisor_snapshot(client):
    r = client.get("/api/capture/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("listening", "connected")
    assert body["paused"] is False
    assert body["shot_count"] == 0
    assert "active_player_id" in body


def test_pause_then_resume_toggles_state(client):
    assert client.post("/api/capture/pause").json()["paused"] is True
    assert client.get("/api/capture/status").json()["paused"] is True
    assert client.post("/api/capture/resume").json()["paused"] is False


def test_active_player_sets_and_reports(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    assert r.status_code == 200
    body = r.json()
    assert body["active_player_id"] is not None
    assert client.get("/api/capture/status").json()["active_player_id"] \
        == body["active_player_id"]


def test_pause_stops_persistence_end_to_end(client, conn):
    # select a player, then pause; a shot fed to the supervisor must be discarded
    client.post("/api/capture/active-player",
                json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    client.post("/api/capture/pause")
    client.supervisor.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    # resume and feed again -> now it persists
    client.post("/api/capture/resume")
    client.supervisor.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_restart_returns_ok(client):
    assert client.post("/api/capture/restart").json()["ok"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_capture.py -v`
Expected: FAIL (404 — routes are still the empty stub).

- [ ] **Step 3: Implement `api_capture.py`**

`web/backend/api_capture.py` (full):
```python
from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from web.backend.deps import get_supervisor

router = APIRouter(prefix="/api/capture", tags=["capture"])


class ActivePlayerIn(BaseModel):
    name: str
    height_in: float
    handedness: str


def _status_dict(sup):
    return asdict(sup.status())


@router.get("/status")
def status(sup=Depends(get_supervisor)):
    return _status_dict(sup)


@router.post("/pause")
def pause(sup=Depends(get_supervisor)):
    sup.pause()
    return _status_dict(sup)


@router.post("/resume")
def resume(sup=Depends(get_supervisor)):
    sup.resume()
    return _status_dict(sup)


@router.post("/restart")
def restart(sup=Depends(get_supervisor)):
    sup.restart()
    return {"ok": True, **_status_dict(sup)}


@router.post("/active-player")
def active_player(body: ActivePlayerIn, sup=Depends(get_supervisor)):
    sup.set_active_player(body.name, body.height_in, body.handedness)
    return _status_dict(sup)
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_capture.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/api_capture.py web/backend/tests/test_api_capture.py
git commit -m "feat(web): capture API (status/pause/resume/restart/active-player)"
```

---

## Task 7: Capture events on the SSE stream

The existing `/events` stream emits `swing_ready`. Extend it to also drain the `CaptureEventBus` and emit `shot_received`, `capture_status`, `active_player_changed` frames — seed-driven (publish to the bus, then read one-shot), no wall-clock sleeps.

**Files:**
- Modify: `web/backend/events.py`
- Create: `web/backend/tests/test_capture_events.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_capture_events.py`:
```python
def test_capture_events_streamed_one_shot(client):
    # publish capture events onto the shared bus, then read /events?once=1
    client.bus.publish("capture_status", {"status": "connected"})
    client.bus.publish("shot_received", {"shot_id": 7, "player_id": 1})
    client.bus.publish("active_player_changed", {"player_id": 1, "name": "Chris"})

    r = client.get("/events", params={"once": 1})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: capture_status" in r.text
    assert "event: shot_received" in r.text
    assert "event: active_player_changed" in r.text
    assert '"shot_id": 7' in r.text


def test_swing_ready_still_emitted_alongside_capture_events(client, conn):
    from web.backend.tests.conftest import seed_player, seed_ready_swing
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    client.bus.publish("capture_status", {"status": "paused"})

    text = client.get("/events", params={"once": 1}).text
    assert "event: swing_ready" in text
    assert f'"swing_id": {ready.id}' in text
    assert "event: capture_status" in text
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_events.py -v`
Expected: FAIL (capture events not emitted; `capture_bus` not consumed).

- [ ] **Step 3: Implement in `events.py`**

Add the bus dependency and a formatter, and drain it inside the generator. Updated `events.py`:
```python
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from web.backend.deps import get_conn, capture_bus

router = APIRouter(tags=["events"])

POLL_INTERVAL_S = 1.5

_READY_SQL = """
SELECT sw.id AS swing_id, sw.session_id, sw.player_id
FROM swing sw
WHERE sw.id > ?
  AND EXISTS (SELECT 1 FROM metric m WHERE m.swing_id = sw.id)
  AND EXISTS (SELECT 1 FROM coaching c WHERE c.swing_id = sw.id)
ORDER BY sw.id
"""


class SwingWatcher:
    def __init__(self, conn, last_id: int = 0):
        self.conn = conn
        self.last_id = last_id

    def poll(self):
        rows = self.conn.execute(_READY_SQL, (self.last_id,)).fetchall()
        events = []
        for r in rows:
            self.last_id = max(self.last_id, r["swing_id"])
            events.append({"swing_id": r["swing_id"],
                           "session_id": r["session_id"],
                           "player_id": r["player_id"]})
        return events


def _format(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.get("/events")
async def events(request: Request, once: int = 0, conn=Depends(get_conn),
                 bus=Depends(capture_bus)):
    watcher = SwingWatcher(conn)

    def _emit_capture():
        return [_format(e["event"], e["data"]) for e in bus.drain()]

    async def gen():
        for e in watcher.poll():
            yield _format("swing_ready", e)
        for frame in _emit_capture():
            yield frame
        if once:
            return
        while True:
            if await request.is_disconnected():
                break
            for e in watcher.poll():
                yield _format("swing_ready", e)
            for frame in _emit_capture():
                yield frame
            yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_S)

    return StreamingResponse(gen(), media_type="text/event-stream")
```

> The `swing_ready` frame now goes through the shared `_format(name, data)` helper
> (previously a dedicated `_format`). Existing `test_events.py` still asserts
> `event: swing_ready` and `"swing_id": N`, which this preserves.

- [ ] **Step 4: Run to verify it passes** (new + existing events tests)

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_capture_events.py web/backend/tests/test_events.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add web/backend/events.py web/backend/tests/test_capture_events.py
git commit -m "feat(web): push capture events (shot/status/player) onto the SSE stream"
```

---

## Task 8: Retire the Tkinter shell + keep the suite green

Delete the standalone catcher UI and its only dependent test, then prove no import breakage across the whole Python suite.

**Files:**
- Delete: `catcher/app.py`, `catcher/run.py`, `catcher/build_exe.md`, `catcher/tests/test_app.py`
- Keep: `catcher/openconnect.py`, `catcher/shotmap.py`, `catcher/sessionmgr.py`, `catcher/persist.py` and `catcher/tests/{test_openconnect,test_persist,test_sessionmgr,test_shotmap}.py`

- [ ] **Step 1: Confirm nothing else imports the retired modules**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest --collect-only -q`
Then search the tree for stragglers:
Run (PowerShell): `Select-String -Path (Get-ChildItem -Recurse -Filter *.py).FullName -Pattern "catcher\.app|catcher\.run|catcher import app|from catcher.app"`
Expected: the only matches are inside `catcher/app.py`, `catcher/run.py`, and `catcher/tests/test_app.py` (all being deleted). `web/backend/capture.py` imports only `openconnect`, `shotmap`, `persist`, `sessionmgr` — which are kept.

- [ ] **Step 2: Delete the retired files**

Run (PowerShell):
```powershell
Remove-Item catcher\app.py, catcher\run.py, catcher\build_exe.md, catcher\tests\test_app.py
```

- [ ] **Step 3: Run the catcher engine tests (must still pass)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/ -v`
Expected: PASS (`test_openconnect`, `test_persist`, `test_sessionmgr`, `test_shotmap`); `test_app` is gone, no collection/import errors.

- [ ] **Step 4: Run the FULL Python suite (no broken imports anywhere)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ catcher/ sync/ web/backend/ -v`
(Include any other top-level test packages present, e.g. `vision/`, `metrics/`, `coach/`, if they exist — use `... -m pytest . -v` to be safe.)
Expected: PASS (all). This is the retirement done-criterion.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(catcher): retire Tkinter shell (app.py/run.py/build_exe.md); engine kept, suite green"
```

---

## Task 9: Kiosk launcher script

A single `.cmd` that starts uvicorn, waits for `/api/health`, then opens the default browser fullscreen at the app URL. Verified by a headless dry-run that exercises the health wait without leaving a browser open.

**Files:**
- Create: `run_garagetec.cmd` (repo root)

- [ ] **Step 1: Write `run_garagetec.cmd`**

`run_garagetec.cmd`:
```bat
@echo off
setlocal
set PY=C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe
set PORT=8000
set URL=http://localhost:%PORT%/

REM Start the unified app (FastAPI serves API + SSE + the built SPA).
start "GarageTEC" /min "%PY%" -m uvicorn web.backend.app:app --host 0.0.0.0 --port %PORT%

REM Wait for health before opening the browser (up to ~30s).
echo Waiting for GarageTEC to come up...
for /L %%i in (1,1,60) do (
  "%PY%" -c "import sys,urllib.request; urllib.request.urlopen('http://localhost:%PORT%/api/health',timeout=1)" 2>nul && goto :ready
  timeout /t 1 /nobreak >nul
)
echo GarageTEC did not become healthy in time.
goto :eof

:ready
echo GarageTEC is up. Launching kiosk...
REM Microsoft Edge in kiosk fullscreen on the touchscreen.
start msedge --kiosk %URL% --edge-kiosk-type=fullscreen --no-first-run
endlocal
```

- [ ] **Step 2: Dry-run the health-wait logic** (no browser, no real server)

The launcher's only non-trivial logic is the health poll. Verify the health endpoint comes up under uvicorn, then stop it:
Run (PowerShell, background):
```powershell
$p = Start-Process -FilePath "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -ArgumentList "-m","uvicorn","web.backend.app:app","--port","8011" -PassThru
```
Then poll health, assert 200, then stop:
```powershell
1..30 | ForEach-Object { try { (Invoke-WebRequest http://localhost:8011/api/health -TimeoutSec 1).StatusCode; break } catch { Start-Sleep -Milliseconds 500 } }
Stop-Process -Id $p.Id
```
Expected: prints `200`. (This proves the same `/api/health` gate the `.cmd` waits on, started by the same uvicorn command. The launcher auto-starts the supervisor through the real lifespan — binding 921 is expected on the mini PC, which is the point; do this dry-run only where port 921 is free or accept a `bind_error` in `last_error` without failing health.)

- [ ] **Step 3: Commit**

```bash
git add run_garagetec.cmd
git commit -m "feat: kiosk launcher (uvicorn + health wait + fullscreen browser)"
```

> Document for later auto-launch-on-boot: add `run_garagetec.cmd` to the mini PC's
> Startup folder (`shell:startup`) or a Scheduled Task at logon. Not automated here.

---

## Task 10: Frontend — capture API client + capture hook

Add the capture data layer (client fns + a hook that holds status and folds in SSE capture events). Pragmatic per the spec; styling deferred.

**Files:**
- Modify: `web/frontend/src/api.js`
- Modify: `web/frontend/src/useEvents.js` (also expose the latest capture event)
- Create: `web/frontend/src/useCapture.js`

- [ ] **Step 1: Extend `api.js`** (append the capture calls)

```javascript
export const getCaptureStatus = () => getJSON("/api/capture/status");
export const pauseCapture = () => postJSON("/api/capture/pause", {});
export const resumeCapture = () => postJSON("/api/capture/resume", {});
export const restartCapture = () => postJSON("/api/capture/restart", {});
export const setActivePlayer = (p) => postJSON("/api/capture/active-player", p);
```

- [ ] **Step 2: Extend `useEvents.js`** to surface capture events too

Make the hook listen for the capture event types and expose the latest one:
```javascript
import { useEffect, useState } from "react";

// Returns { lastSwing, lastCapture } where lastCapture is the most recent
// capture event: { type, data } for shot_received|capture_status|active_player_changed.
export default function useEvents() {
  const [lastSwing, setLastSwing] = useState(null);
  const [lastCapture, setLastCapture] = useState(null);

  useEffect(() => {
    const es = new EventSource("/events");
    const onSwing = (e) => {
      try { setLastSwing(JSON.parse(e.data)); } catch { /* ignore */ }
    };
    const onCapture = (type) => (e) => {
      try { setLastCapture({ type, data: JSON.parse(e.data) }); } catch { /* ignore */ }
    };
    es.addEventListener("swing_ready", onSwing);
    es.addEventListener("shot_received", onCapture("shot_received"));
    es.addEventListener("capture_status", onCapture("capture_status"));
    es.addEventListener("active_player_changed", onCapture("active_player_changed"));
    return () => es.close();
  }, []);

  return { lastSwing, lastCapture };
}
```

> Callers of the old `useEvents()` (Task 14 Live in the Screen plan returned the
> raw swing) must read `.lastSwing` now. Update `Live.jsx` accordingly in Task 12.

- [ ] **Step 3: Write `useCapture.js`**

```javascript
import { useEffect, useState } from "react";
import {
  getCaptureStatus, pauseCapture, resumeCapture, restartCapture, setActivePlayer,
} from "./api";

// Holds capture status; refreshes on mount and whenever a capture SSE event
// arrives (passed in from useEvents). Exposes the control actions.
export default function useCapture(lastCapture) {
  const [status, setStatus] = useState(null);

  const refresh = () => getCaptureStatus().then(setStatus);
  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (lastCapture) refresh(); }, [lastCapture]);

  return {
    status,
    pause: () => pauseCapture().then(setStatus),
    resume: () => resumeCapture().then(setStatus),
    restart: () => restartCapture().then(refresh),
    selectPlayer: (p) => setActivePlayer(p).then(setStatus),
    refresh,
  };
}
```

- [ ] **Step 4: Build smoke (must compile)**

Run: `npm run build --prefix web/frontend`
Expected: `vite build` succeeds (api/hook compile; pages still old until Task 11/12).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/api.js web/frontend/src/useEvents.js web/frontend/src/useCapture.js
git commit -m "feat(web): frontend capture client + useCapture hook + capture SSE events"
```

---

## Task 11: Frontend — GlobalBar + Sidebar (with a component test)

The persistent global bar (player switch + R50 status chip + Pause/Resume) and the left sidebar nav. One vitest component test on the GlobalBar covering status chip text and pause/resume toggle.

**Files:**
- Create: `web/frontend/src/components/GlobalBar.jsx`
- Create: `web/frontend/src/components/Sidebar.jsx`
- Create: `web/frontend/src/components/GlobalBar.test.jsx`

- [ ] **Step 1: Write the failing component test**

`web/frontend/src/components/GlobalBar.test.jsx`:
```javascript
import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import GlobalBar from "./GlobalBar";

const baseProps = {
  players: [{ id: 1, name: "Chris", height_in: 72, handedness: "R" }],
  onSelectPlayer: vi.fn(),
};

describe("GlobalBar", () => {
  it("shows the R50 status chip text from status", () => {
    render(<GlobalBar {...baseProps}
      status={{ status: "connected", paused: false, shot_count: 3,
                active_player_id: 1 }}
      onPause={vi.fn()} onResume={vi.fn()} />);
    expect(screen.getByText(/connected/i)).toBeInTheDocument();
    expect(screen.getByText(/3/)).toBeInTheDocument();
  });

  it("renders Pause when running and calls onPause", () => {
    const onPause = vi.fn();
    render(<GlobalBar {...baseProps}
      status={{ status: "connected", paused: false, shot_count: 0,
                active_player_id: 1 }}
      onPause={onPause} onResume={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /pause/i }));
    expect(onPause).toHaveBeenCalled();
  });

  it("renders Resume and the paused label when paused", () => {
    const onResume = vi.fn();
    render(<GlobalBar {...baseProps}
      status={{ status: "paused", paused: true, shot_count: 0,
                active_player_id: 1 }}
      onPause={vi.fn()} onResume={onResume} />);
    expect(screen.getByText(/not recording/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /resume/i }));
    expect(onResume).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test --prefix web/frontend`
Expected: FAIL (cannot resolve `./GlobalBar`).

- [ ] **Step 3: Implement `GlobalBar.jsx` + `Sidebar.jsx`**

`web/frontend/src/components/GlobalBar.jsx`:
```javascript
export default function GlobalBar({ players, status, onSelectPlayer,
                                    onPause, onResume }) {
  const paused = status?.paused;
  const activeId = status?.active_player_id;
  const chip = paused
    ? "Paused — not recording"
    : status?.status === "connected"
      ? `Connected · ${status?.shot_count ?? 0} shots`
      : status?.status === "listening"
        ? "Waiting for R50…"
        : status?.status || "—";

  return (
    <header className="global-bar">
      <div className="players">
        {players.map((p) => (
          <button key={p.id}
            className={p.id === activeId ? "player active" : "player"}
            onClick={() => onSelectPlayer(p)}>
            {p.name}
          </button>
        ))}
      </div>
      <div className="status-chip">{chip}</div>
      {paused
        ? <button onClick={onResume}>Resume</button>
        : <button onClick={onPause}>Pause</button>}
    </header>
  );
}
```

`web/frontend/src/components/Sidebar.jsx`:
```javascript
import { NavLink } from "react-router-dom";

const LINKS = [
  ["/", "Live"],
  ["/review", "Review"],
  ["/history", "History"],
  ["/sessions", "Sessions"],
  ["/players", "Players"],
  ["/sync", "Sync"],
];

export default function Sidebar() {
  return (
    <nav className="sidebar">
      {LINKS.map(([to, label]) => (
        <NavLink key={to} to={to} end={to === "/"}
          className={({ isActive }) => isActive ? "nav-row active" : "nav-row"}>
          {label}
        </NavLink>
      ))}
      <NavLink to="/connect" className="nav-row pinned">Connect / Settings</NavLink>
    </nav>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test --prefix web/frontend`
Expected: PASS (GlobalBar suite + the existing MetricCard suite).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/GlobalBar.jsx web/frontend/src/components/Sidebar.jsx web/frontend/src/components/GlobalBar.test.jsx
git commit -m "feat(web): GlobalBar (player switch + R50 chip + pause) and Sidebar nav"
```

---

## Task 12: Frontend — Live rework + Connect screen + App layout

Rework Live to the spec 4.3 hierarchy and add the Connect screen, then wire the GlobalBar + Sidebar into `App.jsx` with the new routes. Functional JSX only; styling deferred. Verified by a build smoke (everything compiles) + the existing component tests.

**Files:**
- Modify: `web/frontend/src/pages/Live.jsx`
- Create: `web/frontend/src/pages/Connect.jsx`
- Modify: `web/frontend/src/App.jsx`

- [ ] **Step 1: Rework `Live.jsx`** to the 4.3 hierarchy (hero replay → body metrics → AI read → compact ball/club strip)

`web/frontend/src/pages/Live.jsx`:
```javascript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getSwing, mediaUrl } from "../api";
import MetricCard from "../components/MetricCard";

// Body-movement metric names get top billing; ball/club go to the compact strip.
const BODY_METRICS = new Set([
  "shoulder_tilt_deg", "hip_sway_in", "spine_angle_deg", "early_extension_in",
  "hand_depth_in", "shoulder_turn_deg", "hip_turn_deg",
]);

export default function Live({ lastSwing }) {
  const [detail, setDetail] = useState(null);
  const [slowmo, setSlowmo] = useState(false);
  const [skeleton, setSkeleton] = useState(true);

  useEffect(() => {
    if (lastSwing?.swing_id) getSwing(lastSwing.swing_id).then(setDetail);
  }, [lastSwing]);

  if (!detail) {
    return <main><h1>Waiting for R50… take a shot</h1></main>;
  }

  const { swing, metrics, shot, coaching, media } = detail;
  const annotated = media.find((m) => m.kind === "annotated_video");
  const raw = media.find((m) => m.kind === "source_video") || annotated;
  const video = skeleton ? annotated || raw : raw;
  const read = coaching[0]?.content || {};
  const body = metrics.filter((m) => BODY_METRICS.has(m.name));

  return (
    <main className="live">
      {/* HERO — replay */}
      <section className="hero">
        <h1>Last swing · {swing.club || "—"}{" "}
          <Link to={`/swing/${swing.id}`}>review →</Link></h1>
        {video && (
          <video key={video.path} src={mediaUrl(video.path)} controls
                 width={720}
                 ref={(el) => { if (el) el.playbackRate = slowmo ? 0.25 : 1.0; }} />
        )}
        <div className="hero-controls">
          <button onClick={() => setSlowmo((s) => !s)}>
            {slowmo ? "Realtime" : "Slow-mo"}
          </button>
          <button onClick={() => setSkeleton((s) => !s)}>
            {skeleton ? "Hide skeleton" : "Show skeleton"}
          </button>
        </div>
      </section>

      {/* PRIMARY — body metrics */}
      <section className="body-metrics">
        <h2>Body</h2>
        <div className="cards">
          {body.map((m) => (
            <MetricCard key={m.id} name={m.name} value={m.value} unit={m.unit}
                        lowConfidence={m.method === "estimate"} />
          ))}
        </div>
      </section>

      {/* PRIMARY — AI read */}
      <section className="ai-read">
        <h2>{read.headline || "AI read"}</h2>
        <ul>{(read.findings || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
        {read.drills?.length > 0 && (
          <>
            <h3>Drill</h3>
            <ul>{read.drills.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </>
        )}
      </section>

      {/* SECONDARY — compact ball/club strip */}
      {shot && (
        <section className="ball-club-strip">
          <span>Ball {shot.ball_speed} mph</span>
          <span>Spin {shot.total_spin}</span>
          <span>Launch {shot.vla}°</span>
          <span>Carry {shot.carry}</span>
          {shot.club_speed != null && <span>Club {shot.club_speed} mph</span>}
          {shot.club_path != null && <span>Path {shot.club_path}°</span>}
          {shot.face_to_target != null && <span>Face {shot.face_to_target}°</span>}
          {shot.attack_angle != null && <span>AoA {shot.attack_angle}°</span>}
        </section>
      )}
    </main>
  );
}
```

- [ ] **Step 2: Write `Connect.jsx`** (port the catcher wizard's steps + reconnect)

`web/frontend/src/pages/Connect.jsx`:
```javascript
import useCapture from "../useCapture";

export default function Connect({ lastCapture }) {
  const cap = useCapture(lastCapture);
  const st = cap.status;
  const connected = st?.status === "connected";

  return (
    <main className="connect">
      <h1>Connect your R50</h1>
      <p className="status">
        {connected ? "Connected to your R50"
          : st?.status === "listening" ? "Waiting for your R50…"
          : st?.last_error ? `Problem: ${st.last_error}`
          : "Starting up…"}
      </p>

      <ol className="steps">
        <li>Power on the Garmin Approach R50 and wait for its home screen.</li>
        <li>On the R50, choose <b>Simulator → GSPro</b> (Open Connect).</li>
        <li>Join the same Wi-Fi as this PC (the bay network).</li>
        <li>The R50 will connect automatically — the bar turns
            “Connected”. This app is already listening on port 921.</li>
      </ol>

      <h3>Not connecting?</h3>
      <ul className="troubleshoot">
        <li>Make sure GSPro itself is closed (it also uses port 921).</li>
        <li>Confirm both devices are on the same Wi-Fi.</li>
        <li>Tap reconnect to restart the listener.</li>
      </ul>
      <button onClick={cap.restart}>Reconnect</button>
    </main>
  );
}
```

- [ ] **Step 3: Rewire `App.jsx`** (Sidebar + GlobalBar layout; pass SSE-derived props down)

`web/frontend/src/App.jsx`:
```javascript
import { useEffect, useState } from "react";
import { Routes, Route } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import GlobalBar from "./components/GlobalBar";
import useEvents from "./useEvents";
import useCapture from "./useCapture";
import { getPlayers } from "./api";
import Live from "./pages/Live";
import SwingReview from "./pages/SwingReview";
import Session from "./pages/Session";
import History from "./pages/History";
import SyncFix from "./pages/SyncFix";
import Players from "./pages/Players";
import Connect from "./pages/Connect";

export default function App() {
  const { lastSwing, lastCapture } = useEvents();
  const cap = useCapture(lastCapture);
  const [players, setPlayers] = useState([]);

  useEffect(() => { getPlayers().then(setPlayers); }, [lastCapture]);

  return (
    <div className="app-shell">
      <Sidebar />
      <div className="app-main">
        <GlobalBar players={players} status={cap.status}
          onSelectPlayer={(p) => cap.selectPlayer({
            name: p.name, height_in: p.height_in, handedness: p.handedness })}
          onPause={cap.pause} onResume={cap.resume} />
        <Routes>
          <Route path="/" element={<Live lastSwing={lastSwing} />} />
          <Route path="/swing/:id" element={<SwingReview />} />
          <Route path="/review" element={<SwingReview />} />
          <Route path="/sessions" element={<Session />} />
          <Route path="/session/:id" element={<Session />} />
          <Route path="/history" element={<History />} />
          <Route path="/sync" element={<SyncFix />} />
          <Route path="/players" element={<Players />} />
          <Route path="/connect" element={<Connect lastCapture={lastCapture} />} />
        </Routes>
      </div>
    </div>
  );
}
```

> `SwingReview` and `Session` already read their id from `useParams`; the bare
> `/review` and `/sessions` routes render their loading/empty state until an id is
> chosen (Review/History/Sessions deep-linking is unchanged from the Screen plan).

- [ ] **Step 4: Build smoke (all pages compile)**

Run: `npm run build --prefix web/frontend`
Expected: `vite build` succeeds; `web/frontend/dist/index.html` regenerated.

- [ ] **Step 5: Component tests still pass**

Run: `npm run test --prefix web/frontend`
Expected: PASS (GlobalBar + MetricCard).

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/pages/Live.jsx web/frontend/src/pages/Connect.jsx web/frontend/src/App.jsx
git commit -m "feat(web): Live rework (4.3 hierarchy) + Connect screen + sidebar/global-bar layout"
```

> Deferred per spec section 2 (out of scope): visual styling / design system. The
> CSS classes used here (`global-bar`, `sidebar`, `hero`, `ball-club-strip`, …) are
> placeholders the MagicPatterns pass will dress.

---

## Task 13: Full-suite verification (the done gate)

Prove the whole thing green: backend Python suite (with the new capture modules + retirement) and the frontend build + component tests, served single-origin.

**Files:** (none new — verification only)

- [ ] **Step 1: Full Python suite**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest . -v`
Expected: PASS (all) — includes `store/`, `catcher/` (engine only), `sync/`, `web/backend/` (capture bus, supervisor core + lifecycle, deps, lifespan, capture API, capture events), and any other rocks present. No import errors from the retired shell.

- [ ] **Step 2: Frontend build + tests**

Run: `npm run build --prefix web/frontend`
Then: `npm run test --prefix web/frontend`
Expected: build succeeds; vitest passes (GlobalBar + MetricCard).

- [ ] **Step 3: Manual single-origin smoke (optional, not a gate)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m uvicorn web.backend.app:app --host 0.0.0.0 --port 8000`
Browse `http://localhost:8000/` (SPA shell + global bar), `http://localhost:8000/api/capture/status` (JSON), `http://localhost:8000/api/health`. On a machine with the R50 on the network, hitting a shot should flip the status chip to “Connected · N shots” and populate Live via SSE. Stop with Ctrl+C. (Locally, expect `last_error` to mention `bind_error` only if GSPro is already holding port 921.)

- [ ] **Step 4: Commit (docs/launcher note, if anything changed)**

```bash
git add -A
git commit -m "chore(web): unified app suite green (backend + frontend)"
```

---

## Done criteria

- `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest . -v` is fully green: `CaptureEventBus`, `CaptureSupervisor` core (running/paused/heartbeat, attribute/persist/sync/emit, no-active-player buffering, handedness propagation) and lifecycle (start/stop idempotent, restart, **auto-restart-on-death**), the deps singletons, the FastAPI lifespan, the capture API, and capture SSE events — **none of which bind port 921 or need an R50** (a fake listener is injected throughout).
- Pause semantics proven both in isolation (`handle_message` discards, no persist, no buffer) and end-to-end through `/api/capture/pause`.
- The Tkinter shell (`catcher/app.py`, `run.py`, `build_exe.md`, `tests/test_app.py`) is deleted; the engine modules and their four tests stay green; the full suite imports cleanly.
- `npm run build --prefix web/frontend` succeeds and `npm run test --prefix web/frontend` passes; the app shell has the global bar + sidebar, Live follows the 4.3 hierarchy, and the Connect screen is wired to `/api/capture/*` + SSE.
- `run_garagetec.cmd` starts uvicorn, waits on `/api/health`, and opens a fullscreen browser; the health gate is dry-run verified.
- Visual styling / design system is explicitly deferred (spec section 2).
```
