import pytest
from store import db as dbmod


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()
