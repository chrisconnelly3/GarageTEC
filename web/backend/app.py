"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, api_capture,
    api_settings, events, media, deps,
)


def frontend_dist() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def _resolve_supervisor(app):
    override = app.dependency_overrides.get(deps.get_supervisor)
    return override() if override else deps.get_supervisor()


@asynccontextmanager
async def lifespan(app):
    supervisor = _resolve_supervisor(app)
    supervisor.start()
    try:
        yield
    finally:
        supervisor.stop()


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen", lifespan=lifespan)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(api_players.router)
    app.include_router(api_sessions.router)
    app.include_router(api_swings.router)
    app.include_router(api_history.router)
    app.include_router(api_sync.router)
    app.include_router(api_capture.router)
    app.include_router(api_settings.router)
    app.include_router(events.router)
    app.include_router(media.router)

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True),
                  name="frontend")

    return app


app = create_app()
