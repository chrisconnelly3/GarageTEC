import pytest
from store import db as dbmod
from store import repo


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


@pytest.fixture
def ctx(db):
    """A player + open session. Returns (conn, player_id, session_id)."""
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return db, pid, sid
