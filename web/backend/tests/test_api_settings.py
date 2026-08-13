def test_get_settings_defaults(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json() == {"idle_minutes": 15, "units": "yards", "port": 921,
                        "has_api_key": False, "api_key_hint": ""}


def test_put_settings_merges_and_returns_full(client):
    r = client.put("/api/settings", json={"idle_minutes": 25, "units": "meters"})
    assert r.status_code == 200
    body = r.json()
    assert body["idle_minutes"] == 25 and body["units"] == "meters"
    assert body["port"] == 921  # untouched
    # persisted on a subsequent GET
    assert client.get("/api/settings").json()["idle_minutes"] == 25


def test_put_settings_rejects_bad_units(client):
    r = client.put("/api/settings", json={"units": "furlongs"})
    assert r.status_code == 422


def test_restart_applies_settings_port_and_idle(client, conn):
    # change port + idle, restart; supervisor must pick up both
    client.put("/api/settings", json={"port": 9999, "idle_minutes": 7})
    client.post("/api/capture/restart")
    sup = client.supervisor
    assert sup.port == 9999
    assert sup.session_mgr.idle_minutes == 7
