import json
from store import repo
from store.models import Shot, Coaching


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_unmatched_and_unlink(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    shot = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid))
    assert [s.id for s in repo.list_unmatched_swings(db, session_id=sid)] == [sw.id]
    assert [s.id for s in repo.list_unmatched_shots(db, player_id=pid)] == [shot.id]
    repo.link_shot_to_swing(db, shot.id, sw.id)
    assert repo.list_unmatched_swings(db, session_id=sid) == []
    assert repo.list_unmatched_shots(db, session_id=sid) == []
    repo.unlink_shot(db, sw.id)
    assert [s.id for s in repo.list_unmatched_swings(db, session_id=sid)] == [sw.id]
    assert [s.id for s in repo.list_unmatched_shots(db, session_id=sid)] == [shot.id]


def test_coaching(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    repo.save_coaching(db, Coaching(swing_id=sw.id, session_id=None, kind="swing",
                                    content_json=json.dumps({"headline": "good"}),
                                    model="claude"))
    repo.save_coaching(db, Coaching(swing_id=None, session_id=sid, kind="session",
                                    content_json=json.dumps({"headline": "nice session"})))
    swing_c = repo.get_coaching(db, swing_id=sw.id)
    assert len(swing_c) == 1 and swing_c[0].kind == "swing"
    sess_c = repo.get_coaching(db, session_id=sid)
    assert len(sess_c) == 1 and sess_c[0].kind == "session"
