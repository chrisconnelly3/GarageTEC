import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_db_path():
    root = os.environ.get("GARAGETEC_DATA_DIR")
    base = Path(root) if root else Path(__file__).resolve().parents[1] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "garagetec.db")


def connect(path=None):
    conn = sqlite3.connect(path or default_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(path=None, conn=None):
    conn = conn or connect(path)
    conn.executescript((Path(__file__).parent / "schema.sql").read_text())
    if conn.execute("SELECT version FROM schema_version").fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                     (SCHEMA_VERSION,))
    conn.commit()
    return conn
