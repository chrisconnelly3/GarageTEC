def test_api_still_works_without_built_frontend(client):
    # dist/ does not exist in the test env; API must be unaffected
    assert client.get("/api/health").json() == {"status": "ok"}


def test_serves_index_when_dist_present(tmp_path, monkeypatch):
    import web.backend.app as appmod
    from fastapi.testclient import TestClient

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>GarageTEC</title>")
    monkeypatch.setattr(appmod, "frontend_dist", lambda: dist)

    app = appmod.create_app()
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "GarageTEC" in r.text
