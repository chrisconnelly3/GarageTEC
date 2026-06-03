import pytest
from store import db as dbmod


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


@pytest.fixture
def tmp_buffer(tmp_path):
    return str(tmp_path / "pending_shots.jsonl")
