"""In-process capture engine for the unified app.

CaptureEventBus is a thread-safe buffer of capture events (the listener thread
publishes; the SSE request coroutine drains). CaptureSupervisor (added in the
next task) owns the OpenConnectListener and turns parsed messages into persisted,
synced, broadcast shots.
"""
import threading
from dataclasses import dataclass
from typing import Callable, Optional

from catcher import shotmap
from catcher.openconnect import OpenConnectListener, PORT_DEFAULT
from catcher.persist import ShotPersister
from catcher.sessionmgr import SessionManager
from sync.service import SyncService


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


@dataclass
class CaptureStatus:
    status: str                      # stopped|listening|connected|paused
    paused: bool
    connected: bool
    shot_count: int
    active_player_id: Optional[int]
    active_club: Optional[str]
    last_error: Optional[str]


def _default_listener_factory(**kwargs):
    """Real wrapper: build an OpenConnectListener. Injected fakes replace this
    in tests so no socket is ever opened and port 921 is never bound."""
    return OpenConnectListener(**kwargs)


class CaptureSupervisor:
    """Owns the R50 capture engine inside the FastAPI app.

    `handle_message(obj, source)` is the testable core (no socket/thread):
    running -> map+attribute+persist+sync+emit; paused -> discard; heartbeat ->
    ignore. The listener thread is a thin wrapper that just calls handle_message.
    `listener_factory` is injectable so tests pass a fake.
    """

    def __init__(self, *, conn, bus, listener_factory: Callable = _default_listener_factory,
                 port: int = PORT_DEFAULT, idle_minutes: int = 15,
                 probe_ip: Optional[str] = None, buffer_path: Optional[str] = None,
                 restart_poll_s: float = 1.0, live_capture=None):
        self.conn = conn
        self.bus = bus
        self._listener_factory = listener_factory
        # Optional LiveCaptureSupervisor: when set, a persisted shot auto-triggers
        # a buffered-clip capture that pairs back to this shot. Low-coupling: the
        # live engine just needs an on_shot(player_id, session_id, shot_id) method.
        self.live_capture = live_capture
        self.port = port
        self.probe_ip = probe_ip
        self.restart_poll_s = restart_poll_s

        self.session_mgr = SessionManager(conn, idle_minutes=idle_minutes)
        self.persister = ShotPersister(buffer_path=buffer_path)
        self.sync = SyncService(conn)

        self._lock = threading.Lock()
        self._paused = False
        self._status = "stopped"
        self._connected = False
        self._shot_count = 0
        self.active_club = None          # set via the Live club selector
        self._last_error = None
        self._listener = None
        self._run = False
        self._restarting = False         # guard against double-spawn in restart()
        self._supervisor_thread = None

    # ---- core (directly tested, no socket) -------------------------------
    def handle_message(self, obj: dict, source: str = ""):
        shot = shotmap.map_message(obj)
        if shot is None:
            return None  # heartbeat
        if self._paused:
            return None  # discard: keep R50 connected, do NOT persist/analyze
        if self.session_mgr.active_player is None:
            # No player selected: dropping shot rather than persisting an
            # unattributable orphan (player_id=None rows are invisible to all
            # scoped queries and can never be corrected).
            self.bus.publish("capture_status",
                             {"status": "shot_dropped_no_player",
                              "detail": "no active player; shot discarded"})
            return None
        self.session_mgr.attribute(self.conn, shot)
        shot.club = self.active_club     # tag with the currently-selected club
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
        if self.live_capture is not None:
            try:
                self.live_capture.on_shot(player_id=saved.player_id,
                                          session_id=saved.session_id,
                                          shot_id=saved.id)
            except Exception:
                pass  # live capture is best-effort; never block R50 capture
        return saved

    # ---- settings ---------------------------------------------------------
    def apply_settings(self, settings: dict):
        """Adopt idle_minutes + port from a settings dict. idle takes effect
        immediately (next sweep); port takes effect on the next listener spawn
        (i.e. restart())."""
        if "idle_minutes" in settings:
            self.session_mgr.idle_minutes = int(settings["idle_minutes"])
        if "port" in settings:
            self.port = int(settings["port"])

    # ---- active player ----------------------------------------------------
    def set_active_player(self, name, height_in, handedness):
        player = self.session_mgr.set_active_player(name, height_in, handedness)
        if self._listener is not None:
            self._listener.set_handedness("LH" if handedness == "L" else "RH")
        self.bus.publish("active_player_changed",
                         {"player_id": player.id, "name": player.name})
        return player

    def set_active_club(self, club):
        """The Live club selector sets which club is being hit; every subsequent
        shot is tagged with it (so the 'vs tour' ball comparison is per-club)."""
        self.active_club = club or None
        self.bus.publish("active_club_changed", {"club": self.active_club})
        return self.active_club

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
                active_club=self.active_club,
                last_error=self._last_error)

    # ---- pause/resume -----------------------------------------------------
    def pause(self):
        self._paused = True
        self.bus.publish("capture_status", {"status": "paused"})

    def resume(self):
        self._paused = False
        self.bus.publish("capture_status",
                         {"status": "connected" if self._connected else "listening"})

    # ---- start/stop/restart + supervising loop ----------------------------
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
        with self._lock:
            self._restarting = True
        try:
            if self._listener is not None:
                self._listener.stop()
            self._spawn_listener()
        finally:
            with self._lock:
                self._restarting = False

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
            with self._lock:
                restarting = self._restarting
            if not restarting and self._listener is not None and not self._listener_alive():
                self._last_error = "listener thread died; restarting"
                self.bus.publish("capture_status",
                                 {"status": "restarting"})
                self._spawn_listener()
            time.sleep(self.restart_poll_s)

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
