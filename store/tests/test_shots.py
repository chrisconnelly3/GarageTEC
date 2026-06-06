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


# ---- dedupe / idempotent save_shot ----------------------------------------

def test_save_shot_twice_same_content_one_row(db):
    """Saving the same shot twice yields exactly one DB row; second call returns
    the same id."""
    pid, sid = _ctx(db)
    s = Shot(captured_at="2026-06-05T10:00:00+00:00", player_id=pid,
             session_id=sid, ball_speed=155.0,
             raw_json=json.dumps({"DeviceID": "R50", "ShotNumber": 1}))
    first = repo.save_shot(db, s)
    assert first.id is not None
    # reset id so save_shot sees it as "new"
    s2 = Shot(captured_at="2026-06-05T10:00:00+00:00", player_id=pid,
              session_id=sid, ball_speed=155.0,
              raw_json=json.dumps({"DeviceID": "R50", "ShotNumber": 1}))
    second = repo.save_shot(db, s2)
    assert second.id == first.id
    count = db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"]
    assert count == 1


def test_save_shot_different_content_two_rows(db):
    """Two shots with different raw_json → two distinct rows."""
    pid, sid = _ctx(db)
    s1 = Shot(captured_at="2026-06-05T10:00:00+00:00", player_id=pid,
              session_id=sid, ball_speed=155.0,
              raw_json=json.dumps({"ShotNumber": 1}))
    s2 = Shot(captured_at="2026-06-05T10:00:01+00:00", player_id=pid,
              session_id=sid, ball_speed=160.0,
              raw_json=json.dumps({"ShotNumber": 2}))
    r1 = repo.save_shot(db, s1)
    r2 = repo.save_shot(db, s2)
    assert r1.id != r2.id
    count = db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"]
    assert count == 2


def test_save_shot_raw_json_dedupe(db):
    """Identical raw_json dedupes; different raw_json does not."""
    pid, sid = _ctx(db)
    rj_a = json.dumps({"BallData": {"Speed": 148.0}, "ShotNumber": 7})
    rj_b = json.dumps({"BallData": {"Speed": 149.0}, "ShotNumber": 8})
    a1 = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid,
                                 raw_json=rj_a))
    a2 = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid,
                                 raw_json=rj_a))
    b1 = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid,
                                 raw_json=rj_b))
    assert a1.id == a2.id          # same raw_json → same row
    assert b1.id != a1.id          # different raw_json → new row
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 2


def test_save_shot_no_raw_json_gets_null_dedupe_key(db):
    """Shots without raw_json get dedupe_key=None and are always inserted fresh.
    The partial UNIQUE index only fires for non-NULL keys, so two synthetic shots
    with identical numeric fields still create two rows (they are distinct events)."""
    pid, sid = _ctx(db)
    kwargs = dict(captured_at="2026-06-05T10:00:00+00:00", player_id=pid,
                  session_id=sid, ball_speed=142.0)
    r1 = repo.save_shot(db, Shot(**kwargs))
    r2 = repo.save_shot(db, Shot(**kwargs))
    assert r1.id != r2.id          # two different rows
    assert r1.dedupe_key is None   # no key assigned
    assert r2.dedupe_key is None
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 2


def test_crash_replay_no_duplicate(db):
    """Simulated crash-replay: first save succeeds (shot in DB), then the same
    shot is saved again (as replay would do) → no duplicate, same id returned."""
    pid, sid = _ctx(db)
    s = Shot(captured_at="2026-06-05T10:00:00+00:00", player_id=pid,
             session_id=sid, ball_speed=161.5,
             raw_json=json.dumps({"DeviceID": "R50", "ShotNumber": 99}))
    original = repo.save_shot(db, s)
    assert original.id is not None
    # simulate replay: reconstruct shot from buffer (no id)
    replayed = repo.save_shot(db, Shot(
        captured_at="2026-06-05T10:00:00+00:00", player_id=pid, session_id=sid,
        ball_speed=161.5,
        raw_json=json.dumps({"DeviceID": "R50", "ShotNumber": 99})))
    assert replayed.id == original.id
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1
