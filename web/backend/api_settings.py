import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from store import repo
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    idle_minutes: Optional[int] = None
    units: Optional[str] = None
    port: Optional[int] = None
    anthropic_api_key: Optional[str] = None


def _masked(settings: dict) -> dict:
    """Never let the raw anthropic_api_key leave this process over the API.
    Replaces it with has_api_key/api_key_hint (last-4 only)."""
    key = settings.get("anthropic_api_key") or ""
    out = {k: v for k, v in settings.items() if k != "anthropic_api_key"}
    out["has_api_key"] = bool(key)
    out["api_key_hint"] = f"sk-ant-…{key[-4:]}" if key else ""
    return out


@router.get("")
def get_settings(conn=Depends(get_conn)):
    return _masked(repo.get_settings(conn))


@router.put("")
def put_settings(body: SettingsIn, conn=Depends(get_conn)):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if "units" in values and values["units"] not in ("yards", "meters"):
        raise HTTPException(status_code=422, detail="units must be yards|meters")
    if "idle_minutes" in values and values["idle_minutes"] < 1:
        raise HTTPException(status_code=422, detail="idle_minutes must be >= 1")
    if "port" in values and not (1 <= values["port"] <= 65535):
        raise HTTPException(status_code=422, detail="port out of range")
    if "anthropic_api_key" in values:
        key = values["anthropic_api_key"]
        if key and not key.startswith("sk-"):
            raise HTTPException(
                status_code=422, detail="that does not look like an Anthropic API key")
        # Export immediately so the running process picks it up without a
        # restart; empty string means "clear it".
        if key:
            os.environ["ANTHROPIC_API_KEY"] = key
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)
    return _masked(repo.save_settings(conn, values))
