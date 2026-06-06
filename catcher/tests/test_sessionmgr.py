from store import repo
from store.models import Shot
from catcher.sessionmgr import SessionManager


def _shot():
    # captured_at is overwritten by attribute(); player/session start empty
    return Shot(captured_at="placeholder", ball_speed=120.0)


def _attribute_and_save(mgr, db):
    """Mirror the real pipeline: attribute() stamps the shot, then it is
    persisted via repo.save_shot (sessionmgr.attribute itself persists
    nothing). Returns the saved Shot (with id)."""
    shot = mgr.attribute(db, _shot())
    return repo.save_shot(db, shot)


def test_set_active_creates_player_and_tracks(db):
    mgr = SessionManager(db, idle_minutes=15)
    p = mgr.set_active_player("Chris", height_in=72.0, handedness="R")
    assert p.id is not None
    assert mgr.active_player.id == p.id


def test_attribute_opens_one_session_and_resumes_it(db):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    s1 = mgr.attribute(db, _shot())
    s2 = mgr.attribute(db, _shot())
    assert s1.player_id == mgr.active_player.id
    assert s1.session_id is not None
    # second shot for the same player resumes the same open session
    assert s2.session_id == s1.session_id


def test_brother_you_interleave_resumes_each_session(db):
    mgr = SessionManager(db, idle_minutes=15)

    # brother hits
    mgr.set_active_player("Brother", 70.0, "R")
    b1 = _attribute_and_save(mgr, db)
    bro_session = b1.session_id
    bro_id = mgr.active_player.id

    # switch to you, you hit
    mgr.set_active_player("Chris", 72.0, "R")
    y1 = _attribute_and_save(mgr, db)
    you_session = y1.session_id
    you_id = mgr.active_player.id

    # different player => different session, different player_id
    assert you_id != bro_id
    assert you_session != bro_session

    # switch back to brother within the idle window => his SAME session resumes
    mgr.set_active_player("Brother", 70.0, "R")
    b2 = _attribute_and_save(mgr, db)
    assert b2.player_id == bro_id
    assert b2.session_id == bro_session

    # each person's shots stayed theirs
    bro_shots = db.execute(
        "SELECT player_id, session_id FROM shot WHERE player_id=?",
        (bro_id,)).fetchall()
    assert all(r["session_id"] == bro_session for r in bro_shots)
    assert len(bro_shots) == 2
    you_shots = db.execute(
        "SELECT session_id FROM shot WHERE player_id=?", (you_id,)).fetchall()
    assert len(you_shots) == 1 and you_shots[0]["session_id"] == you_session


def test_idle_timeout_starts_a_new_session(db):
    from datetime import datetime, timezone, timedelta
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    first = _attribute_and_save(mgr, db)

    # backdate the saved shot to 30 minutes ago so the session looks idle
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    db.execute("UPDATE shot SET captured_at=? WHERE id=?", (old, first.id))
    db.commit()

    # sweep idle sessions (what the periodic timer calls), then hit again
    closed = mgr.sweep_idle(db)
    assert closed == 1
    second = mgr.attribute(db, _shot())
    assert second.session_id != first.session_id  # a fresh session opened


def test_attribute_without_active_player_raises(db):
    mgr = SessionManager(db, idle_minutes=15)
    try:
        mgr.attribute(db, _shot())
        assert False, "expected an error when no active player is set"
    except RuntimeError:
        pass


def test_attribute_preserves_existing_captured_at(db):
    """Fix 3: attribute() must NOT overwrite captured_at when the shot mapper
    has already set one (used for idle-session timing)."""
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    mapper_ts = "2026-06-03T12:00:00+00:00"
    shot = Shot(captured_at=mapper_ts, ball_speed=110.0)
    result = mgr.attribute(db, shot)
    assert result.captured_at == mapper_ts, (
        "attribute() clobbered the mapper-supplied captured_at")


def test_attribute_sets_captured_at_when_missing(db):
    """Fix 3: attribute() should set captured_at only when it is absent."""
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    shot = Shot(captured_at=None, ball_speed=110.0)
    result = mgr.attribute(db, shot)
    assert result.captured_at is not None and result.captured_at != ""
