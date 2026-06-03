from store import repo


def _player(db, name="Chris"):
    return repo.get_or_create_player(db, name, 72.0, "R").id


def test_get_session_returns_row_or_none(db):
    assert repo.get_session(db, 999) is None
    pid = _player(db)
    s = repo.create_session(db, pid, location="bay")
    got = repo.get_session(db, s.id)
    assert got is not None
    assert got.id == s.id and got.player_id == pid and got.location == "bay"


def test_list_sessions_all_and_by_player_newest_first(db):
    a = _player(db, "A")
    b = _player(db, "B")
    s_a1 = repo.create_session(db, a)
    s_b1 = repo.create_session(db, b)
    s_a2 = repo.create_session(db, a)
    all_ids = [s.id for s in repo.list_sessions(db)]
    assert all_ids == [s_a2.id, s_b1.id, s_a1.id]  # newest id first
    a_ids = [s.id for s in repo.list_sessions(db, player_id=a)]
    assert a_ids == [s_a2.id, s_a1.id]
