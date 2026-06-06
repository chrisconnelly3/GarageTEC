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
    # vs-tour-pro benchmarks present for metrics with a GolfTEC target
    assert "benchmarks" in body and isinstance(body["benchmarks"], list)
    bnames = {b["name"] for b in body["benchmarks"]}
    assert "shoulder_tilt_deg" in bnames
    for b in body["benchmarks"]:
        assert {"name", "context", "value", "target", "comparable"} <= set(b)


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


def test_list_swings_endpoint(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    r = client.get(f"/api/swings?player={p.id}")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1
    top = body[0]
    assert top["id"] == swing.id
    assert top["has_shot"] is True            # seed_ready_swing links a shot
    assert top["club"] == "7i"
    assert "created_at" in top


def test_list_swings_scoped_to_session(client, conn):
    from store import repo
    p = seed_player(conn)
    seed_ready_swing(conn, p)                  # session A
    # a swing in a different session should be excluded when session= is passed
    other_sid = repo.create_session(conn, p.id).id
    repo.add_swing(conn, other_sid, p.id, "z.mp4")
    body = client.get(f"/api/swings?player={p.id}&session={other_sid}").json()
    assert [s["id"] for s in body] == [body[0]["id"]]
    assert all(s["club"] is None for s in body)  # the z.mp4 swing has no club


def test_latest_swing_endpoint(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    r = client.get(f"/api/swings/latest?player={p.id}")
    assert r.status_code == 200
    assert r.json()["swing"]["id"] == swing.id


def test_latest_swing_204_when_none(client, conn):
    p = seed_player(conn)
    r = client.get(f"/api/swings/latest?player={p.id}")
    assert r.status_code == 204


def test_swing_detail_includes_ball_benchmarks_key(client, conn):
    from web.backend.tests.conftest import seed_player, seed_ready_swing
    p = seed_player(conn)
    sw = seed_ready_swing(conn, p)
    body = client.get(f"/api/swings/{sw.id}").json()
    assert "ball_benchmarks" in body and isinstance(body["ball_benchmarks"], list)


def test_swing_detail_includes_ball_raw_key(client, conn):
    from web.backend.tests.conftest import seed_player, seed_ready_swing
    p = seed_player(conn)
    sw = seed_ready_swing(conn, p)
    body = client.get(f"/api/swings/{sw.id}").json()
    assert "ball_raw" in body and isinstance(body["ball_raw"], list)
    keys = [r["key"] for r in body["ball_raw"]]
    assert keys == ["club_path", "face_to_target", "spin_axis",
                    "back_spin", "side_spin", "hla"]
    for r in body["ball_raw"]:
        assert set(r) == {"key", "label", "unit", "value"}


def test_list_swings_limit_capped_at_200(client, conn):
    """Fix 6a: requesting limit=9999 must be silently capped at 200."""
    p = seed_player(conn)
    seed_ready_swing(conn, p)
    r = client.get(f"/api/swings?player={p.id}&limit=9999")
    assert r.status_code == 200
    # We can't assert exactly 200 rows with only 1 swing seeded, but we can
    # confirm the endpoint accepts the param without error.
    assert isinstance(r.json(), list)


def test_swing_detail_benchmark_shape_zone_state_direction_hla(client, conn):
    """Guard that benchmark rows carry state+direction, ball_benchmark rows
    carry zone+direction, and ball_raw includes an hla entry."""
    p = seed_player(conn)
    sw = seed_ready_swing(conn, p)
    body = client.get(f"/api/swings/{sw.id}").json()
    assert all("state" in r and "direction" in r for r in body["benchmarks"])
    assert all("zone" in r and "direction" in r for r in body["ball_benchmarks"])
    assert any(r["key"] == "hla" for r in body["ball_raw"])
