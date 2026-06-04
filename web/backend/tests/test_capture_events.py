def test_capture_events_streamed_one_shot(client):
    # publish capture events onto the shared bus, then read /events?once=1
    client.bus.publish("capture_status", {"status": "connected"})
    client.bus.publish("shot_received", {"shot_id": 7, "player_id": 1})
    client.bus.publish("active_player_changed", {"player_id": 1, "name": "Chris"})

    r = client.get("/events", params={"once": 1})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: capture_status" in r.text
    assert "event: shot_received" in r.text
    assert "event: active_player_changed" in r.text
    assert '"shot_id": 7' in r.text


def test_swing_ready_still_emitted_alongside_capture_events(client, conn):
    from web.backend.tests.conftest import seed_player, seed_ready_swing
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    client.bus.publish("capture_status", {"status": "paused"})

    text = client.get("/events", params={"once": 1}).text
    assert "event: swing_ready" in text
    assert f'"swing_id": {ready.id}' in text
    assert "event: capture_status" in text
