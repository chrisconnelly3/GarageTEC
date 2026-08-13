import os

import pytest

from store import repo


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Other tests in the suite may depend on ANTHROPIC_API_KEY being absent;
    # never let this file leak state either direction.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


def test_get_unset_key_has_no_raw_value(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    body = r.json()
    assert body["has_api_key"] is False
    assert body["api_key_hint"] == ""
    assert "anthropic_api_key" not in body


def test_put_valid_key_masks_response_and_exports_env(client):
    raw_key = "sk-ant-abc123f3Ah"
    r = client.put("/api/settings", json={"anthropic_api_key": raw_key})
    assert r.status_code == 200
    body = r.json()
    assert body["has_api_key"] is True
    assert body["api_key_hint"].endswith("f3Ah")
    assert "anthropic_api_key" not in body
    assert raw_key not in r.text  # the full raw key must never appear in the body
    assert os.environ["ANTHROPIC_API_KEY"] == raw_key


def test_put_empty_string_clears_key(client):
    client.put("/api/settings", json={"anthropic_api_key": "sk-ant-abc123f3Ah"})
    r = client.put("/api/settings", json={"anthropic_api_key": ""})
    assert r.status_code == 200
    body = r.json()
    assert body["has_api_key"] is False
    assert body["api_key_hint"] == ""
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_put_malformed_key_rejected(client):
    r = client.put("/api/settings", json={"anthropic_api_key": "not-a-key"})
    assert r.status_code == 422
    assert "ANTHROPIC_API_KEY" not in os.environ


def test_roundtrip_stores_real_value_in_db(client, conn):
    client.put("/api/settings", json={"anthropic_api_key": "sk-ant-realvalue1234"})
    assert repo.get_settings(conn)["anthropic_api_key"] == "sk-ant-realvalue1234"
