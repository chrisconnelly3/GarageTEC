from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from store import repo
from web.backend.capture import NoActivePlayerError
from web.backend.deps import get_conn, get_supervisor

router = APIRouter(prefix="/api/capture", tags=["capture"])

_HEIGHT_MIN = 36.0   # 3 ft – smallest plausible golfer
_HEIGHT_MAX = 96.0   # 8 ft – largest plausible golfer


class ActivePlayerIn(BaseModel):
    name: str
    height_in: float
    handedness: str

    @field_validator("handedness")
    @classmethod
    def _validate_handedness(cls, v: str) -> str:
        if v not in {"R", "L"}:
            raise ValueError("handedness must be 'R' or 'L'")
        return v

    @field_validator("height_in")
    @classmethod
    def _validate_height(cls, v: float) -> float:
        if not (_HEIGHT_MIN <= v <= _HEIGHT_MAX):
            raise ValueError(
                f"height_in must be between {_HEIGHT_MIN} and {_HEIGHT_MAX}")
        return v


class ActiveClubIn(BaseModel):
    club: str | None = None


def _status_dict(sup):
    return asdict(sup.status())


@router.get("/status")
def status(sup=Depends(get_supervisor)):
    return _status_dict(sup)


@router.post("/start-session")
def start_session(sup=Depends(get_supervisor)):
    """Open a new recording session for the active player and turn recording
    ON. 409 if no active player (nothing to attribute shots to)."""
    try:
        sup.start_session()
    except NoActivePlayerError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return _status_dict(sup)


@router.post("/end-session")
def end_session(sup=Depends(get_supervisor)):
    """End the active recording session and turn recording OFF."""
    sup.end_session()
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
