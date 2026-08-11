"""Additive enrichment channel for OpenFlight launch monitors.

OpenFlight streams shots to us over GSPro OpenConnect (TCP 921), but that wire
format cannot express whether a number was measured or modelled. Its own web UI
gets the full truth over Socket.IO, so we subscribe to the same `shot` event and
recover per-field source/confidence plus real nulls.

Strictly additive: this module never persists anything and never blocks shot
ingest. If OpenFlight is unreachable or its payload shape changes, shots keep
arriving over the socket and simply fall back to conservative trust tiers.

We call OpenFlight's API over the network; no OpenFlight code is imported or
vendored (it is AGPL-3.0, this project is MIT).
"""
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_WEB_PORT = 8080          # OpenFlight's Flask/Socket.IO default (--web-port)
MDNS_HOST = "openflight.local"   # advertised via Avahi by OpenFlight
SHOT_EVENT = "shot"


def url_for_host(host: str, port: int = DEFAULT_WEB_PORT) -> str:
    """Base HTTP URL for an OpenFlight host."""
    return f"http://{host}:{port}"


def normalize_event(payload) -> Optional[dict]:
    """Extract the shot dict from a Socket.IO `shot` event payload.

    Accepts both the documented `{"shot": {...}, "stats": {...}}` envelope and a
    bare shot dict. Returns None for anything unusable, including a shot with no
    ball speed (the correlation key). Unknown extra keys are preserved so the
    trust policy can use them if it learns to.
    """
    if not isinstance(payload, dict):
        return None
    shot = payload.get("shot") if isinstance(payload.get("shot"), dict) else payload
    if not isinstance(shot, dict):
        return None
    speed = shot.get("ball_speed_mph")
    try:
        float(speed)
    except (TypeError, ValueError):
        return None
    return shot


class OpenFlightEnrichClient:
    """Connects to one OpenFlight host and forwards normalized shot records.

    `on_enrichment(record: dict)` is called for every usable shot event.
    `on_status(state: str, detail: str)` reports "connected" / "disconnected" /
    "unavailable" for the Connect screen.
    """

    def __init__(self, host: str, *, port: int = DEFAULT_WEB_PORT,
                 on_enrichment: Optional[Callable[[dict], None]] = None,
                 on_status: Optional[Callable[[str, str], None]] = None):
        self.host = host
        self.port = port
        self.on_enrichment = on_enrichment or (lambda record: None)
        self.on_status = on_status or (lambda state, detail: None)
        self._sio = None
        self._thread = None
        self._running = False

    @property
    def url(self) -> str:
        return url_for_host(self.host, self.port)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        sio = self._sio
        if sio is not None:
            try:
                sio.disconnect()
            except Exception:
                pass

    def is_connected(self) -> bool:
        sio = self._sio
        return bool(sio is not None and getattr(sio, "connected", False))

    def _run(self) -> None:
        try:
            import socketio  # python-socketio[client]
        except ImportError:
            # Optional dependency: degrade to no enrichment rather than crash.
            logger.info("[openflight] python-socketio missing; enrichment disabled")
            self.on_status("unavailable", "python-socketio not installed")
            self._running = False
            return

        # The library owns reconnect/backoff; we just keep the client alive.
        sio = socketio.Client(reconnection=True, reconnection_delay=2,
                              reconnection_delay_max=30, logger=False,
                              engineio_logger=False)
        self._sio = sio

        @sio.event
        def connect():
            self.on_status("connected", self.url)

        @sio.event
        def disconnect():
            self.on_status("disconnected", self.url)

        @sio.on(SHOT_EVENT)
        def _on_shot(payload):
            record = normalize_event(payload)
            if record is None:
                return
            try:
                self.on_enrichment(record)
            except Exception:
                logger.debug("[openflight] enrichment handler failed", exc_info=True)

        try:
            sio.connect(self.url, transports=["websocket", "polling"])
            sio.wait()
        except Exception as e:
            # Unreachable host, refused connection, protocol error: all non-fatal.
            logger.info("[openflight] enrichment unavailable at %s: %s", self.url, e)
            self.on_status("disconnected", str(e))
        finally:
            self._running = False
