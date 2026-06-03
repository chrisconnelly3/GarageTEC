import json
from store import repo
from store.models import Shot


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_save_shot_and_fields(db):
    pid, sid = _ctx(db)
    shot = Shot(captured_at="2026-06-03T00:00:00+00:00", player_id=pid,
                session_id=sid, ball_speed=148.2, total_spin=2710.0, vla=13.8,
                club_path=2.1, raw_json=json.dumps({"DeviceID": "R50"}))
    saved = repo.save_shot(db, shot)
    assert saved.id is not None and saved.ball_speed == 148.2


def test_link_shot_and_swing_both_directions(db):
    pid, sid = _ctx(db)
    shot = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid))
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    repo.link_shot_to_swing(db, shot.id, sw.id)
    assert repo.get_swing(db, sw.id).shot_id == shot.id
    row = db.execute("SELECT swing_id FROM shot WHERE id=?", (shot.id,)).fetchone()
    assert row["swing_id"] == sw.id


def test_get_shot_by_id(db):
    pid, sid = _ctx(db)
    saved = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:00+00:00",
                                    player_id=pid, session_id=sid,
                                    ball_speed=148.2, club_speed=98.0))
    got = repo.get_shot(db, saved.id)
    assert got is not None and got.id == saved.id
    assert got.ball_speed == 148.2 and got.club_speed == 98.0
    assert repo.get_shot(db, 999999) is None
