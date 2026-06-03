from datetime import datetime, timezone, timedelta
from store import repo


def _player(db):
    return repo.get_or_create_player(db, "Chris", 72.0, "R").id


def test_open_session_and_resume(db):
    pid = _player(db)
    assert repo.get_open_session(db, pid) is None
    s = repo.create_session(db, pid)
    assert s.id is not None and s.ended_at is None
    assert repo.get_open_session(db, pid).id == s.id  # resumes the open one


def test_end_idle_sessions_closes_stale_only(db):
    pid = _player(db)
    s = repo.create_session(db, pid)
    # a shot 30 min ago => stale
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    repo.save_shot(db, _shot(pid, s.id, old))
    closed = repo.end_idle_sessions(db, idle_minutes=15)
    assert closed == 1
    assert repo.get_open_session(db, pid) is None


def test_end_idle_sessions_keeps_recent(db):
    pid = _player(db)
    s = repo.create_session(db, pid)
    from store.db import now_iso
    repo.save_shot(db, _shot(pid, s.id, now_iso()))
    assert repo.end_idle_sessions(db, idle_minutes=15) == 0
    assert repo.get_open_session(db, pid).id == s.id


def _shot(pid, sid, ts):
    from store.models import Shot
    return Shot(captured_at=ts, player_id=pid, session_id=sid, ball_speed=100.0)
