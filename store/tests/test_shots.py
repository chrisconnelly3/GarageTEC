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


# ---- shot_history -------------------------------------------------------

def _shot(db, pid, sid, *, at, **kw):
    return repo.save_shot(db, Shot(captured_at=at, player_id=pid,
                                   session_id=sid, **kw))


def test_shot_history_ordered_ascending_and_excludes_null(db):
    pid, sid = _ctx(db)
    # out-of-order inserts; one row has a null ball_speed and must be excluded
    _shot(db, pid, sid, at="2026-06-03T00:00:02+00:00", ball_speed=150.0)
    _shot(db, pid, sid, at="2026-06-03T00:00:01+00:00", ball_speed=148.0)
    _shot(db, pid, sid, at="2026-06-03T00:00:03+00:00", ball_speed=None)
    rows = repo.shot_history(db, pid, "ball_speed")
    assert [v for (_, _, v) in rows] == [148.0, 150.0]   # ascending, null gone


def test_shot_history_club_filter(db):
    pid, sid = _ctx(db)
    _shot(db, pid, sid, at="t1", ball_speed=120.0, club="7 Iron")
    _shot(db, pid, sid, at="t2", ball_speed=167.0, club="Driver")
    rows = repo.shot_history(db, pid, "ball_speed", club="Driver")
    assert [v for (_, _, v) in rows] == [167.0]


def test_shot_history_derived_smash(db):
    pid, sid = _ctx(db)
    _shot(db, pid, sid, at="t1", ball_speed=148.0, club_speed=100.0)
    _shot(db, pid, sid, at="t2", ball_speed=130.0, club_speed=None)  # excluded
    rows = repo.shot_history(db, pid, "smash")
    assert [v for (_, _, v) in rows] == [round(148.0 / 100.0, 2)]


def test_shot_history_launch_alias_of_vla(db):
    pid, sid = _ctx(db)
    _shot(db, pid, sid, at="t1", vla=13.8)
    rows = repo.shot_history(db, pid, "launch")
    assert [v for (_, _, v) in rows] == [13.8]


def test_shot_history_spin_alias_of_total_spin(db):
    pid, sid = _ctx(db)
    _shot(db, pid, sid, at="t1", total_spin=7100.0)
    rows = repo.shot_history(db, pid, "spin")
    assert [v for (_, _, v) in rows] == [7100.0]


def test_shot_history_rejects_unknown_metric(db):
    pid, sid = _ctx(db)
    import pytest
    with pytest.raises(ValueError):
        repo.shot_history(db, pid, "raw_json; DROP TABLE shot")
    with pytest.raises(ValueError):
        repo.shot_history(db, pid, "club")
