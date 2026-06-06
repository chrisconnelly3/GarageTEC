SHOT_MSG = {
    "DeviceID": "R50", "ShotNumber": 1,
    "BallData": {"Speed": 148.0, "VLA": 13.0, "CarryDistance": 172.0},
    "ShotDataOptions": {"IsHeartBeat": False},
}


def test_status_returns_supervisor_snapshot(client):
    r = client.get("/api/capture/status")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("listening", "connected")
    assert body["paused"] is False
    assert body["shot_count"] == 0
    assert "active_player_id" in body


def test_pause_then_resume_toggles_state(client):
    assert client.post("/api/capture/pause").json()["paused"] is True
    assert client.get("/api/capture/status").json()["paused"] is True
    assert client.post("/api/capture/resume").json()["paused"] is False


def test_active_player_sets_and_reports(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    assert r.status_code == 200
    body = r.json()
    assert body["active_player_id"] is not None
    assert client.get("/api/capture/status").json()["active_player_id"] \
        == body["active_player_id"]


def test_pause_stops_persistence_end_to_end(client, conn):
    # select a player + start a session, then pause; a shot fed to the
    # supervisor must be discarded (pause still gates inside an active session)
    client.post("/api/capture/active-player",
                json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    client.post("/api/capture/start-session")
    client.post("/api/capture/pause")
    client.supervisor.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0
    # resume and feed again -> now it persists
    client.post("/api/capture/resume")
    client.supervisor.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


# ---- Start/End Session recording gate -------------------------------------

def test_start_session_without_player_returns_409(client):
    r = client.post("/api/capture/start-session")
    assert r.status_code == 409
    assert "player" in r.json()["detail"].lower()


def test_start_session_with_player_reports_active(client):
    client.post("/api/capture/active-player",
                json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    r = client.post("/api/capture/start-session")
    assert r.status_code == 200
    body = r.json()
    assert body["session_active"] is True
    assert body["active_session_id"] is not None
    # status endpoint reflects it too
    st = client.get("/api/capture/status").json()
    assert st["session_active"] is True
    assert st["active_session_id"] == body["active_session_id"]


def test_end_session_turns_recording_off(client, conn):
    client.post("/api/capture/active-player",
                json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    started = client.post("/api/capture/start-session").json()
    sid = started["active_session_id"]
    r = client.post("/api/capture/end-session")
    assert r.status_code == 200
    body = r.json()
    assert body["session_active"] is False
    assert body["active_session_id"] is None
    row = conn.execute("SELECT ended_at FROM session WHERE id=?", (sid,)).fetchone()
    assert row["ended_at"] is not None


def test_status_includes_session_fields(client):
    body = client.get("/api/capture/status").json()
    assert body["session_active"] is False
    assert body["active_session_id"] is None


def test_shot_dropped_when_no_session_end_to_end(client, conn):
    # player selected but no session started -> shots are gated out
    client.post("/api/capture/active-player",
                json={"name": "Chris", "height_in": 72.0, "handedness": "R"})
    client.supervisor.handle_message(SHOT_MSG, source="t")
    assert conn.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_restart_returns_ok(client):
    assert client.post("/api/capture/restart").json()["ok"] is True


def test_clubs_list_endpoint(client):
    clubs = client.get("/api/capture/clubs").json()
    assert clubs[0] == "Driver" and clubs[-1] == "PW" and "7 Iron" in clubs


def test_active_club_sets_and_reports(client):
    r = client.post("/api/capture/active-club", json={"club": "7 Iron"})
    assert r.status_code == 200 and r.json()["active_club"] == "7 Iron"
    assert client.get("/api/capture/status").json()["active_club"] == "7 Iron"
    # clearing
    assert client.post("/api/capture/active-club",
                       json={"club": None}).json()["active_club"] is None


# ---- Fix 4: active-player input validation --------------------------------

def test_active_player_invalid_handedness_returns_422(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Chris", "height_in": 72.0,
                          "handedness": "X"})
    assert r.status_code == 422


def test_active_player_height_too_low_returns_422(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Chris", "height_in": 20.0,
                          "handedness": "R"})
    assert r.status_code == 422


def test_active_player_height_too_high_returns_422(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Chris", "height_in": 200.0,
                          "handedness": "R"})
    assert r.status_code == 422


def test_active_player_left_handed_valid(client):
    r = client.post("/api/capture/active-player",
                    json={"name": "Lefty", "height_in": 68.0,
                          "handedness": "L"})
    assert r.status_code == 200
