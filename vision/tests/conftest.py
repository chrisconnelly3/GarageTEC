import os
import pytest
from store import db as dbmod

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TEST_VIDEO = os.path.join(REPO_ROOT, "golf swing.MOV")


def has_test_video():
    return os.path.exists(TEST_VIDEO)


requires_video = pytest.mark.skipif(
    not has_test_video(), reason="golf swing.MOV not present at repo root")


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()
