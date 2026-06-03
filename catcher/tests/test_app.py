import os
import subprocess
import sys

from store import repo
from catcher.app import ShotPipeline
from catcher.sessionmgr import SessionManager
from catcher.persist import ShotPersister


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_persists_shot_for_active_player(db, tmp_buffer):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    persister = ShotPersister(buffer_path=tmp_buffer)
    pipeline = ShotPipeline(db, mgr, persister)

    msg = {"DeviceID": "R50", "ShotNumber": 1,
           "BallData": {"Speed": 148.0, "VLA": 13.0, "TotalSpin": 2700.0},
           "ShotDataOptions": {"IsHeartBeat": False}}
    saved = pipeline.handle(msg, source="test")
    assert saved is not None
    assert saved.player_id == mgr.active_player.id
    assert saved.session_id is not None
    assert saved.ball_speed == 148.0
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_pipeline_ignores_heartbeat(db, tmp_buffer):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    pipeline = ShotPipeline(db, mgr, ShotPersister(buffer_path=tmp_buffer))
    out = pipeline.handle({"ShotDataOptions": {"IsHeartBeat": True}}, source="t")
    assert out is None
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_pipeline_buffers_when_no_active_player(db, tmp_buffer):
    # a shot arriving before anyone is selected must not be lost: it buffers
    mgr = SessionManager(db, idle_minutes=15)
    pipeline = ShotPipeline(db, mgr, ShotPersister(buffer_path=tmp_buffer))
    out = pipeline.handle(
        {"DeviceID": "R50", "ShotNumber": 1,
         "BallData": {"Speed": 99.0},
         "ShotDataOptions": {"IsHeartBeat": False}}, source="t")
    assert out is None
    assert os.path.exists(tmp_buffer)
    assert pipeline.persister.pending_count() == 1


def test_selftest_constructs_headlessly():
    # tkinter ships with Python; --selftest builds the window and tears it down
    result = subprocess.run(
        [sys.executable, "-m", "catcher.run", "--selftest"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "selftest ok" in result.stdout
