"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
