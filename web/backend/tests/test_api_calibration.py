# web/backend/tests/test_api_calibration.py
from fastapi.testclient import TestClient
from web.backend.app import create_app
from web.backend import deps


class _FakeSup:
    def __init__(self): self._poses = 0; self.started = None
    def start(self, **kw): self.started = kw
    def stop(self): pass
    def run(self): return {"ok": True, "n_poses": 12, "reprojection_error": 0.4}
    def status(self): return {"capturing": True, "good_poses": self._poses,
                              "coverage": [], "device_index": 0, "cols": 9, "rows": 6}
    def latest_overlay_jpeg(self): return b"\xff\xd8jpeg\xff\xd9"


def _client():
    app = create_app()
    fake = _FakeSup()
    app.dependency_overrides[deps.get_calibration_supervisor] = lambda: fake
    return TestClient(app), fake


def test_start_stop_run_status():
    client, fake = _client()
    r = client.post("/api/calibration/start",
                    json={"device_index": 0, "cols": 9, "rows": 6, "square_mm": 25.0})
    assert r.status_code == 200 and fake.started["cols"] == 9
    assert client.get("/api/calibration/status").json()["cols"] == 9
    assert client.post("/api/calibration/run").json()["ok"] is True
    assert client.post("/api/calibration/stop").status_code == 200


def test_preview_streams_jpeg():
    """Verify the /preview endpoint is registered and declares MJPEG content-type.

    The endpoint is an infinite MJPEG generator — TestClient blocks waiting for the
    generator to exhaust, so we verify the content-type via the route's response
    class directly (without making an HTTP request) and confirm the route is
    registered in the app.
    """
    from web.backend import api_calibration as _ac  # the router module we just created
    app = create_app()
    fake = _FakeSup()
    app.dependency_overrides[deps.get_calibration_supervisor] = lambda: fake

    # 1. Route is registered
    routes = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/calibration/preview" in routes

    # 2. Calling the endpoint handler directly returns a StreamingResponse with
    #    the correct media_type (no HTTP round-trip needed for content-type check).
    import asyncio
    resp = asyncio.run(_ac.preview(sup=fake))
    assert "multipart/x-mixed-replace" in resp.media_type
