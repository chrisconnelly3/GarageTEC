"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from a repo-root .env into the environment (without
    overriding existing vars). Lets the AI coach pick up ANTHROPIC_API_KEY for
    local dev without committing the secret. No external dependency."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        # Set when absent OR currently blank (some shells export an empty
        # ANTHROPIC_API_KEY, which setdefault would wrongly preserve). A real
        # non-empty value already in the environment still wins.
        if not os.environ.get(key):
            os.environ[key] = value.strip()


_load_dotenv()

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, api_capture,
    api_settings, api_calibration, api_live_capture, events, media, deps,
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
    app.include_router(api_history.ball_router)
    app.include_router(api_sync.router)
    app.include_router(api_capture.router)
    app.include_router(api_settings.router)
    app.include_router(api_calibration.router)
    app.include_router(api_live_capture.router)
    app.include_router(events.router)
    app.include_router(media.router)

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True),
                  name="frontend")

    return app


app = create_app()
