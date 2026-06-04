from store import repo
from store.models import Player


def test_create_and_list_player(db):
    p = repo.get_or_create_player(db, "Chris", 72.0, "R")
    assert p.id is not None and p.created_at is not None
    again = repo.get_or_create_player(db, "Chris", 72.0, "R")
    assert again.id == p.id  # same name => same row, not a duplicate
    repo.get_or_create_player(db, "Brother", 70.0, "R")
    names = sorted(pl.name for pl in repo.list_players(db))
    assert names == ["Brother", "Chris"]


def test_player_swing_and_session_counts(db):
    from store import repo
    p = repo.get_or_create_player(db, "Cnt", 70.0, "R")
    s1 = repo.create_session(db, p.id).id
    s2 = repo.create_session(db, p.id).id
    repo.add_swing(db, s1, p.id, "a.mp4")
    repo.add_swing(db, s1, p.id, "b.mp4")
    repo.add_swing(db, s2, p.id, "c.mp4")
    assert repo.count_swings_for_player(db, p.id) == 3
    assert repo.count_sessions_for_player(db, p.id) == 2
    # a different player is isolated
    other = repo.get_or_create_player(db, "Other", 70.0, "L")
    assert repo.count_swings_for_player(db, other.id) == 0


def test_get_player_by_id(db):
    p = repo.get_or_create_player(db, "Heighted", 73.0, "R")
    got = repo.get_player(db, p.id)
    assert got.id == p.id and got.height_in == 73.0 and got.handedness == "R"
    assert repo.get_player(db, 99999) is None
