def test_supervisor_started_on_app_startup(client):
    # entering the TestClient context ran lifespan startup
    assert client.supervisor.status().status in ("listening", "connected")


def test_supervisor_stopped_on_shutdown(conn, supervisor, bus, tmp_path):
    from fastapi.testclient import TestClient
    from web.backend.app import create_app
    from web.backend import deps

    app = create_app()
    app.dependency_overrides[deps.get_conn] = lambda: conn
    app.dependency_overrides[deps.get_supervisor] = lambda: supervisor
    app.dependency_overrides[deps.capture_bus] = lambda: bus
    media = tmp_path / "m"; media.mkdir()
    app.dependency_overrides[deps.media_root] = lambda: media
    with TestClient(app):
        assert supervisor.status().status != "stopped"
    # context exit ran lifespan shutdown
    assert supervisor.status().status == "stopped"
