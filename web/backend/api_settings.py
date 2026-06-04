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


@router.get("")
def get_settings(conn=Depends(get_conn)):
    return repo.get_settings(conn)


@router.put("")
def put_settings(body: SettingsIn, conn=Depends(get_conn)):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if "units" in values and values["units"] not in ("yards", "meters"):
        raise HTTPException(status_code=422, detail="units must be yards|meters")
    if "idle_minutes" in values and values["idle_minutes"] < 1:
        raise HTTPException(status_code=422, detail="idle_minutes must be >= 1")
    if "port" in values and not (1 <= values["port"] <= 65535):
        raise HTTPException(status_code=422, detail="port out of range")
    return repo.save_settings(conn, values)
