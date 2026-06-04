"""Request-scoped dependencies for the Screen backend.

`get_conn` yields a store connection per request; tests override it with an
in-memory connection. `media_root` returns the directory media is served from;
tests override it with a temp dir.
"""
import sqlite3
from pathlib import Path

from store import db as dbmod
from store import repo

from web.backend.capture import CaptureEventBus, CaptureSupervisor
from web.backend.calibration import CalibrationEventBus, CalibrationSupervisor


def get_conn():
    # check_same_thread=False: FastAPI runs sync deps in a worker thread while
    # async endpoints (e.g. the /events SSE generator) iterate on the event-loop
    # thread; a default connection would raise "SQLite objects created in a
    # thread can only be used in that same thread". The connection is
    # request-scoped and closed below, so no two threads use it concurrently.
    conn = sqlite3.connect(dbmod.default_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
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
        conn = _listener_conn()
        settings = repo.get_settings(conn)
        _supervisor = CaptureSupervisor(
            conn=conn, bus=capture_bus(),
            port=settings["port"], idle_minutes=settings["idle_minutes"])
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


_calibration_bus = None
_calibration_supervisor = None


def calibration_bus() -> CalibrationEventBus:
    global _calibration_bus
    if _calibration_bus is None:
        _calibration_bus = CalibrationEventBus()
    return _calibration_bus


def get_calibration_supervisor() -> CalibrationSupervisor:
    global _calibration_supervisor
    if _calibration_supervisor is None:
        _calibration_supervisor = CalibrationSupervisor(
            conn=_listener_conn(), bus=calibration_bus())
    return _calibration_supervisor


def reset_calibration_singletons():
    global _calibration_bus, _calibration_supervisor
    if _calibration_supervisor is not None:
        try: _calibration_supervisor.stop()
        except Exception: pass
    _calibration_bus = None
    _calibration_supervisor = None
