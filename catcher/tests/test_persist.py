import json
import os

from store import repo
from store.models import Shot
from catcher.persist import ShotPersister


def _player_session(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def _shot(pid, sid, speed):
    return Shot(captured_at="2026-06-03T00:00:00+00:00", player_id=pid,
                session_id=sid, ball_speed=speed,
                raw_json=json.dumps({"BallData": {"Speed": speed}}))


def test_save_success_writes_to_store_and_no_buffer(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)
    saved = p.save(db, _shot(pid, sid, 100.0))
    assert saved.id is not None
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1
    assert not os.path.exists(tmp_buffer) or os.path.getsize(tmp_buffer) == 0
    assert p.pending_count() == 0


def test_save_failure_buffers_to_file(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)

    class BoomConn:
        def execute(self, *a, **k):
            raise RuntimeError("database is locked")

    # store raises => shot must be buffered, not lost, and not raised to caller
    result = p.save(BoomConn(), _shot(pid, sid, 142.0))
    assert result is None  # signals "buffered, not yet persisted"
    assert os.path.exists(tmp_buffer)
    lines = [l for l in open(tmp_buffer, encoding="utf-8").read().splitlines() if l]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["ball_speed"] == 142.0
    assert p.pending_count() == 1
    # DB itself untouched
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_replay_drains_buffer_into_recovered_store(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)

    class BoomConn:
        def execute(self, *a, **k):
            raise RuntimeError("database is locked")

    p.save(BoomConn(), _shot(pid, sid, 101.0))
    p.save(BoomConn(), _shot(pid, sid, 102.0))
    assert p.pending_count() == 2

    # DB recovers: replay drains the buffer into the real store
    replayed = p.replay(db)
    assert replayed == 2
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 2
    speeds = sorted(r["ball_speed"] for r in
                    db.execute("SELECT ball_speed FROM shot").fetchall())
    assert speeds == [101.0, 102.0]
    # buffer cleared after successful replay
    assert p.pending_count() == 0
    assert not os.path.exists(tmp_buffer) or os.path.getsize(tmp_buffer) == 0


def test_replay_with_empty_buffer_is_noop(db, tmp_buffer):
    p = ShotPersister(buffer_path=tmp_buffer)
    assert p.replay(db) == 0
