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
