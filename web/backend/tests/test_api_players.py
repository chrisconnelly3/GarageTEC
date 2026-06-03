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


def test_create_player_is_idempotent_by_name(client, conn):
    seed_player(conn, "Chris")
    r = client.post("/api/players", json={"name": "Chris", "height_in": 72.0,
                                          "handedness": "R"})
    assert r.status_code == 200
    assert len(client.get("/api/players").json()) == 1  # no duplicate row
