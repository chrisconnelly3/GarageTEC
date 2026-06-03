"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from fastapi import FastAPI

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, events, media,
)


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
    return app
