def test_lan_ip_is_nonempty_string(client):
    r = client.get("/api/capture/setup-info")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["lan_ip"], str) and body["lan_ip"]


def test_port_matches_stored_setting(client):
    client.put("/api/settings", json={"port": 9321})
    body = client.get("/api/capture/setup-info").json()
    assert body["port"] == 9321


def test_openflight_connector_shape(client):
    body = client.get("/api/capture/setup-info").json()
    connector = body["openflight_connector"]["connectors"][0]
    assert connector["device_id"] == "OpenFlight"
    assert connector["host"] == body["lan_ip"]
    assert connector["port"] == body["port"]
