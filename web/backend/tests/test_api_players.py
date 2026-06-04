from web.backend.tests.conftest import seed_player


def test_list_players_empty(client):
    assert client.get("/api/players").json() == []


def test_create_then_list_players(client):
    r = client.post("/api/players", json={"name": "Chris", "height_in": 72.0,
                                          "handedness": "R"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] is not None and body["name"] == "Chris"

    names = [p["name"] for p in client.get("/api/players").json()]
    assert names == ["Chris"]


def test_players_include_counts(client, conn):
    from store import repo
    p = repo.get_or_create_player(conn, "Counter", 71.0, "R")
    sid = repo.create_session(conn, p.id).id
    repo.add_swing(conn, sid, p.id, "x.mp4")
    repo.add_swing(conn, sid, p.id, "y.mp4")
    body = client.get("/api/players").json()
    row = next(r for r in body if r["id"] == p.id)
    assert row["swing_count"] == 2
    assert row["session_count"] == 1
    # base player fields still present
    assert row["name"] == "Counter" and row["handedness"] == "R"


def test_create_player_is_idempotent_by_name(client, conn):
    seed_player(conn, "Chris")
    r = client.post("/api/players", json={"name": "Chris", "height_in": 72.0,
                                          "handedness": "R"})
    assert r.status_code == 200
    assert len(client.get("/api/players").json()) == 1  # no duplicate row
