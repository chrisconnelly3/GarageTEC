import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

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


def _add_column_if_missing(conn, table, col, decl):
    """Idempotent ALTER for columns added to existing tables (CREATE TABLE IF NOT
    EXISTS only covers fresh DBs).

    table and col are asserted to be safe SQL identifiers (defense-in-depth;
    all callers today pass hardcoded literals)."""
    assert _IDENT_RE.match(table), f"unsafe table name: {table!r}"
    assert _IDENT_RE.match(col), f"unsafe column name: {col!r}"
    cols = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
    if col not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl}")


def init_db(path=None, conn=None):
    conn = conn or connect(path)
    conn.executescript((Path(__file__).parent / "schema.sql").read_text())
    # lightweight migrations for columns added to pre-existing tables
    _add_column_if_missing(conn, "shot", "club", "TEXT")
    _add_column_if_missing(conn, "shot", "dedupe_key", "TEXT")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_shot_dedupe "
        "ON shot(dedupe_key) WHERE dedupe_key IS NOT NULL"
    )
    if conn.execute("SELECT version FROM schema_version").fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                     (SCHEMA_VERSION,))
    conn.commit()
    return conn
