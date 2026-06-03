"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, events, media,
)


def frontend_dist() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(api_players.router)
    app.include_router(api_sessions.router)
    app.include_router(api_swings.router)
    app.include_router(api_history.router)
    app.include_router(api_sync.router)
    app.include_router(events.router)
    app.include_router(media.router)

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True),
                  name="frontend")

    return app


app = create_app()
