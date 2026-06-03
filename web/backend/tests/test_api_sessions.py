from web.backend.tests.conftest import seed_player, seed_ready_swing


def test_list_sessions_filter_by_player(client, conn):
    a = seed_player(conn, "A")
    b = seed_player(conn, "B")
    seed_ready_swing(conn, a)
    seed_ready_swing(conn, b)

    all_sessions = client.get("/api/sessions").json()
    assert len(all_sessions) == 2

    a_only = client.get("/api/sessions", params={"player": a.id}).json()
    assert len(a_only) == 1 and a_only[0]["player_id"] == a.id


def test_get_session_includes_swings(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    sid = swing.session_id

    r = client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == sid
    assert [s["id"] for s in body["swings"]] == [swing.id]
    assert body["swings"][0]["shot_id"] is not None
    assert body["coaching"] == []  # no session-level coaching seeded


def test_get_missing_session_404(client):
    assert client.get("/api/sessions/999").status_code == 404
