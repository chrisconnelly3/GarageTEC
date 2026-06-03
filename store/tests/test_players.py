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


def test_get_player_by_id(db):
    p = repo.get_or_create_player(db, "Heighted", 73.0, "R")
    got = repo.get_player(db, p.id)
    assert got.id == p.id and got.height_in == 73.0 and got.handedness == "R"
    assert repo.get_player(db, 99999) is None
