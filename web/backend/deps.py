"""Request-scoped dependencies for the Screen backend.

`get_conn` yields a store connection per request; tests override it with an
in-memory connection. `media_root` returns the directory media is served from;
tests override it with a temp dir.
"""
from pathlib import Path

from store import db as dbmod


def get_conn():
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    try:
        yield conn
    finally:
        conn.close()


def media_root() -> Path:
    return Path(dbmod.default_db_path()).parent / "media"
