from fastapi import APIRouter, Depends, HTTPException, Response

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import (
    swing_dict, metric_dict, moment_dict, shot_dict, coaching_dict, media_dict,
)

router = APIRouter(prefix="/api/swings", tags=["swings"])


@router.get("")
def list_swings(player: int | None = None, session: int | None = None,
                limit: int = 50, conn=Depends(get_conn)):
    return repo.list_swing_summaries(conn, player_id=player,
                                     session_id=session, limit=limit)


@router.get("/latest")
def latest_swing(player: int, session: int | None = None,
                 conn=Depends(get_conn)):
    swing = repo.latest_ready_swing(conn, player, session_id=session)
    if swing is None:
        return Response(status_code=204)
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return {
        "swing": swing_dict(swing),
        "metrics": [metric_dict(m) for m in repo.get_metrics(conn, swing.id)],
        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing.id)],
        "shot": shot_dict(shot),
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing.id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing.id)],
    }


@router.get("/{swing_id}")
def get_swing(swing_id: int, conn=Depends(get_conn)):
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise HTTPException(status_code=404, detail="swing not found")
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return {
        "swing": swing_dict(swing),
        "metrics": [metric_dict(m) for m in repo.get_metrics(conn, swing_id)],
        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing_id)],
        "shot": shot_dict(shot),
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing_id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing_id)],
    }
