"""Request-scoped dependencies for the Screen backend.

`get_conn` yields a store connection per request; tests override it with an
in-memory connection. `media_root` returns the directory media is served from;
tests override it with a temp dir.
"""
import sqlite3
from pathlib import Path

from store import db as dbmod

from web.backend.capture import CaptureEventBus, CaptureSupervisor


def get_conn():
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    try:
        yield conn
    finally:
        conn.close()


def media_root() -> Path:
    return Path(dbmod.default_db_path()).parent / "media"


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
