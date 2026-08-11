"""In-process capture engine for the unified app.

CaptureEventBus is a thread-safe buffer of capture events (the listener thread
publishes; the SSE request coroutine drains). CaptureSupervisor (added in the
next task) owns the OpenConnectListener and turns parsed messages into persisted,
synced, broadcast shots.
"""
import json
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

from catcher import shotmap
from catcher.enrich_buffer import EnrichBuffer, SPEED_TOLERANCE
from catcher.openconnect import OpenConnectListener, PORT_DEFAULT
from catcher.openflight_enrich import OpenFlightEnrichClient
from catcher.persist import ShotPersister
from catcher.sessionmgr import SessionManager
from store import db as dbmod
from store import repo
from sync.service import SyncService


# How long a persisted shot stays eligible for late enrichment.
_ENRICH_WINDOW_S = 5.0


@dataclass
class _RecentShot:
    """A persisted shot still eligible for late enrichment."""
    shot_id: int
    ball_speed: float
    ts: float
    enriched: bool = False


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
    session_active: bool             # is a recording session open + gating ON
    active_session_id: Optional[int] # id of the session shots attribute to


class NoActivePlayerError(ValueError):
    """Raised by start_session() when no player is selected. The API maps this
    to HTTP 409 (cannot start recording without someone to attribute shots to)."""


# GarageTEC club names -> GSPro Open Connect club codes.
_GSPRO_CLUB_CODES = {
    "Driver": "DR", "3 Wood": "W3", "5 Wood": "W5", "Hybrid": "H3",
    "3 Iron": "I3", "4 Iron": "I4", "5 Iron": "I5", "6 Iron": "I6",
    "7 Iron": "I7", "8 Iron": "I8", "9 Iron": "I9", "PW": "PW",
}


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
                 restart_poll_s: float = 1.0, live_capture=None,
                 enrich_client_factory: Callable = OpenFlightEnrichClient):
        self.conn = conn
        self.bus = bus
        self._listener_factory = listener_factory
        self._enrich_client_factory = enrich_client_factory
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
        # Recording gate: the R50 listener always listens, but shots are only
        # persisted while a session is actively recording. start_session() turns
        # this on (and opens the session shots attribute to); end_session() off.
        self._recording = False
        self._active_session_id = None
        self._status = "stopped"
        self._connected = False
        self._shot_count = 0
        # OpenFlight enrichment: additive, discovered from the inbound connection.
        self._enrich_buffer = EnrichBuffer()
        self._enrich_client = None
        self._enrich_lock = threading.Lock()
        # Recently persisted shots still eligible for late enrichment.
        self._recent_shots: list = []
        self.openflight_host = None
        self.enrichment_status = "idle"
        self.active_club = None          # set via the Live club selector
        self._last_error = None
        self._listener = None
        self._run = False
        self._restarting = False         # guard against double-spawn in restart()
        self._supervisor_thread = None

    def on_enrichment(self, record: dict):
        """Callback for the OpenFlight enrichment client.

        Correlation is bidirectional because the channels race: OpenFlight emits
        its Socket.IO event and sends the OpenConnect payload from the same
        handler, so either can arrive first.
          * enrichment first -> buffer it for handle_message() to claim
          * shot first       -> attach it to the row we just persisted
        """
        if self._attach_to_recent_shot(record.get("ball_speed_mph"), record):
            return
        self._enrich_buffer.add_enrichment(record)

    def _attach_to_recent_shot(self, ball_speed, record) -> bool:
        """Attach `record` to a recent, not-yet-enriched shot. Returns whether
        the record was CLAIMED (matched to a shot slot) — not whether the DB
        write succeeded. A failed write still forfeits the record (the slot
        stays marked enriched, no retry): if we returned False here instead,
        on_enrichment() would re-buffer the record and it would drift onto a
        later, unrelated shot."""
        try:
            target = float(ball_speed)
        except (TypeError, ValueError):
            return False
        cutoff = time.monotonic() - _ENRICH_WINDOW_S
        # Both channels emit in shot order, so the oldest eligible slot is the
        # right pairing (FIFO) — matches EnrichBuffer.take_for. Scanning
        # newest-first (reversed) would pair a late enrichment to the wrong
        # shot whenever two same-speed shots are pending at once.
        with self._enrich_lock:
            for entry in self._recent_shots:
                if entry.enriched or entry.ts < cutoff:
                    continue
                if abs(entry.ball_speed - target) <= SPEED_TOLERANCE:
                    entry.enriched = True
                    shot_id = entry.shot_id
                    break
            else:
                return False
        try:
            # Writes through the supervisor's own connection from the
            # Socket.IO client thread; safe because deps.py opens it with
            # check_same_thread=False, but it departs from the "fresh
            # connection per thread" convention documented in live_capture.py.
            repo.set_shot_enrichment(self.conn, shot_id, json.dumps(record))
        except Exception:
            pass  # enrichment must never break ingest; slot stays claimed
        return True

    def _note_recent_shot(self, shot):
        """Make a persisted shot eligible for late enrichment."""
        if shot.ball_speed is None:
            return
        now = time.monotonic()
        with self._enrich_lock:
            self._recent_shots = [e for e in self._recent_shots
                                  if e.ts >= now - _ENRICH_WINDOW_S]
            self._recent_shots.append(
                _RecentShot(shot.id, float(shot.ball_speed), now))

    def note_source(self, device_id, source: str):
        """Learn the OpenFlight host from the connection it opened to us, and
        start the enrichment client the first time we see that device.

        `source` is "ip:port" for inbound connections or "PROBE->ip:port" for the
        outbound probe path.
        """
        if device_id != "OpenFlight" or not source:
            return
        addr = source.split("->")[-1]
        host = addr.rsplit(":", 1)[0].strip()
        if not host:
            return
        # Check-and-set under the lock: the listener is thread-per-connection,
        # so two threads could otherwise both see openflight_host is None and
        # each start a client, orphaning one.
        with self._enrich_lock:
            if host == self.openflight_host:
                return
            self.openflight_host = host
        self._start_enrichment(host)

    def _start_enrichment(self, host: str):
        if self._enrich_client is not None:
            self._enrich_client.stop()

        def _status(state, detail):
            self.enrichment_status = state
            self.bus.publish("enrichment_status", {"state": state, "detail": detail})

        self._enrich_client = self._enrich_client_factory(
            host, on_enrichment=self.on_enrichment, on_status=_status)
        self._enrich_client.start()

    # ---- core (directly tested, no socket) -------------------------------
    def handle_message(self, obj: dict, source: str = ""):
        shot = shotmap.map_message(obj)
        if shot is None:
            return None  # heartbeat
        self.note_source(shot.device_id, source)
        if not self._recording or self._active_session_id is None:
            # No active recording session: the listener stays connected but the
            # shot is dropped (not persisted, not buffered). Recording is gated
            # by an explicit Start Session; mirrors the no-player drop pattern.
            self.bus.publish("capture_status",
                             {"status": "shot_dropped_no_session",
                              "detail": "no active session; shot discarded"})
            return None
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
        # Attribute to the explicitly-started session (not an arbitrary
        # auto-created one): stamp player + the active session directly.
        shot.player_id = self.session_mgr.active_player.id
        shot.session_id = self._active_session_id
        if not shot.captured_at:
            shot.captured_at = dbmod.now_iso()
        shot.club = self.active_club     # tag with the currently-selected club
        enrichment = self._enrich_buffer.take_for(shot.ball_speed)
        if enrichment is not None:
            shot.enrichment_json = json.dumps(enrichment)
        saved = self.persister.save(self.conn, shot)
        if saved is None:
            return None  # buffered on DB failure; nothing to sync/emit yet
        if saved.enrichment_json is None:
            self._note_recent_shot(saved)
            # Close the take_for/_note_recent_shot window: an enrichment that
            # landed during the INSERT is buffered but was claimable by neither
            # path. Re-poll AFTER registering, or the gap just moves.
            late = self._enrich_buffer.take_for(saved.ball_speed)
            if late is not None:
                self._attach_to_recent_shot(saved.ball_speed, late)
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
        code = _GSPRO_CLUB_CODES.get(self.active_club or "")
        if code and self._listener is not None:
            try:
                self._listener.send_player_update(club=code)
            except Exception:
                pass  # pushing club is best-effort; never block the UI
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
                last_error=self._last_error,
                session_active=self._recording,
                active_session_id=self._active_session_id)

    # ---- session recording gate ------------------------------------------
    def start_session(self) -> CaptureStatus:
        """Open a NEW recording session for the active player and turn the
        recording gate ON. While ON, incoming R50 shots are persisted and
        attributed to this session. Requires an active player.

        Raises NoActivePlayerError (a ValueError) if no player is selected."""
        ap = self.session_mgr.active_player
        if ap is None:
            raise NoActivePlayerError(
                "cannot start a session: no active player selected")
        session = repo.create_session(self.conn, ap.id)
        with self._lock:
            self._active_session_id = session.id
            self._recording = True
        self.bus.publish("capture_status",
                         {"status": "session_started",
                          "session_id": session.id, "player_id": ap.id})
        return self.status()

    def end_session(self) -> CaptureStatus:
        """End the active recording session (if any) and turn the recording
        gate OFF. While OFF, incoming R50 shots are dropped (not persisted)."""
        with self._lock:
            sid = self._active_session_id
            self._active_session_id = None
            self._recording = False
        if sid is not None:
            repo.end_session(self.conn, sid)
        self.bus.publish("capture_status",
                         {"status": "session_ended", "session_id": sid})
        return self.status()

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
        if self._enrich_client is not None:
            self._enrich_client.stop()
            self._enrich_client = None
        self.openflight_host = None

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
