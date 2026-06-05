from dataclasses import asdict

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from store import repo
from web.backend.deps import get_conn, get_supervisor

router = APIRouter(prefix="/api/capture", tags=["capture"])


class ActivePlayerIn(BaseModel):
    name: str
    height_in: float
    handedness: str


class ActiveClubIn(BaseModel):
    club: str | None = None


def _status_dict(sup):
    return asdict(sup.status())


@router.get("/status")
def status(sup=Depends(get_supervisor)):
    return _status_dict(sup)


@router.post("/pause")
def pause(sup=Depends(get_supervisor)):
    sup.pause()
    return _status_dict(sup)


@router.post("/resume")
def resume(sup=Depends(get_supervisor)):
    sup.resume()
    return _status_dict(sup)


@router.post("/restart")
def restart(sup=Depends(get_supervisor), conn=Depends(get_conn)):
    sup.apply_settings(repo.get_settings(conn))
    sup.restart()
    return {"ok": True, **_status_dict(sup)}


@router.post("/active-player")
def active_player(body: ActivePlayerIn, sup=Depends(get_supervisor)):
    sup.set_active_player(body.name, body.height_in, body.handedness)
    return _status_dict(sup)


@router.get("/clubs")
def clubs():
    """Club options for the Live club selector (TrackMan reference order)."""
    from coach.ball_reference import CLUBS
    return CLUBS


@router.post("/active-club")
def active_club(body: ActiveClubIn, sup=Depends(get_supervisor)):
    sup.set_active_club(body.club)
    return _status_dict(sup)
