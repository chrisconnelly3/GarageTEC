"""API: /api/live-capture start/stop/status + SSE stream registration."""
from fastapi.testclient import TestClient

from web.backend.app import create_app
from web.backend import deps


class _FakeLive:
    def __init__(self):
        self._running = False
        self.started = None

    def start(self, **kw):
        self.started = kw
        self._running = True

    def stop(self):
        self._running = False

    def status(self):
        return {"running": self._running, "capturing": self._running,
                "source": "none", "buffered_frames": 0, "swing_count": 0,
                "fps": 30.0, "window_s": 4.0, "post_shot_delay_s": 0.6,
                "last_error": None}


def _client():
    app = create_app()
    fake = _FakeLive()
    app.dependency_overrides[deps.get_live_capture_supervisor] = lambda: fake
    return TestClient(app), fake


def test_status_endpoint():
    client, _ = _client()
    r = client.get("/api/live-capture/status")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False
    assert body["source"] == "none"
    assert "buffered_frames" in body


def test_start_and_stop():
    client, fake = _client()
    r = client.post("/api/live-capture/start",
                    json={"device_left": 1, "device_right": 2,
                          "window_s": 5.0, "fps": 60.0})
    assert r.status_code == 200
    assert fake.started["device_left"] == 1
    assert fake.started["device_right"] == 2
    assert fake.started["window_s"] == 5.0
    assert fake.started["fps"] == 60.0
    assert client.get("/api/live-capture/status").json()["running"] is True
    assert client.post("/api/live-capture/stop").status_code == 200
    assert client.get("/api/live-capture/status").json()["running"] is False


def test_start_defaults_are_optional():
    client, fake = _client()
    r = client.post("/api/live-capture/start", json={})
    assert r.status_code == 200
    assert "device_left" in fake.started


def test_stream_route_registered_and_sse_content_type():
    import asyncio
    from web.backend import api_live_capture as _alc
    from web.backend.capture import CaptureEventBus

    app = create_app()
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/live-capture/stream" in routes

    bus = CaptureEventBus()
    bus.publish("live_capture_status", {"running": True})

    class _Req:
        async def is_disconnected(self):
            return True
    resp = asyncio.run(_alc.stream(request=_Req(), bus=bus))
    assert "text/event-stream" in resp.media_type
