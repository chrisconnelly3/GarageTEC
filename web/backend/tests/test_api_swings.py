from web.backend.tests.conftest import seed_player, seed_ready_swing


def test_swing_detail_aggregates_everything(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)

    r = client.get(f"/api/swings/{swing.id}")
    assert r.status_code == 200
    body = r.json()

    assert body["swing"]["id"] == swing.id and body["swing"]["club"] == "7i"
    names = {m["name"] for m in body["metrics"]}
    assert names == {"shoulder_tilt_deg", "hip_sway_in"}
    kinds = [m["kind"] for m in body["moments"]]
    assert kinds == ["address", "impact"]  # ordered by frame_index
    assert body["shot"]["ball_speed"] == 148.2
    assert body["coaching"][0]["content"]["headline"] == "Solid contact"
    assert body["media"][0]["kind"] == "annotated_video"


def test_swing_detail_unmatched_has_null_shot(client, conn):
    from store import repo
    p = seed_player(conn)
    sid = repo.create_session(conn, p.id).id
    swing = repo.add_swing(conn, sid, p.id, "v.mp4")

    body = client.get(f"/api/swings/{swing.id}").json()
    assert body["shot"] is None
    assert body["metrics"] == [] and body["coaching"] == []


def test_missing_swing_404(client):
    assert client.get("/api/swings/999").status_code == 404
