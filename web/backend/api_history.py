from fastapi import APIRouter, Depends, HTTPException

from store import repo
from coach import ball_reference
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/history", tags=["history"])

# Separate router for the ball-metric trend endpoint (different path prefix).
ball_router = APIRouter(prefix="/api/ball-history", tags=["history"])


@router.get("")
def history(player: int, metric: str, context: str = "overall",
            conn=Depends(get_conn)):
    rows = repo.swing_history(conn, player, metric, context=context)
    return {
        "player": player,
        "metric": metric,
        "context": context,
        "points": [{"swing_id": sid, "created_at": ts, "value": value}
                   for (sid, ts, value) in rows],
    }


@ball_router.get("")
def ball_history(player: int, metric: str, club: str | None = None,
                 conn=Depends(get_conn)):
    """Ball-metric trend over time, optionally filtered by club, with the
    TrackMan tour-average target for (metric, club) when available.
    `metric` is one of repo.SHOT_HISTORY_METRICS keys."""
    try:
        rows = repo.shot_history(conn, player, metric, club=club)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "player": player,
        "metric": metric,
        "club": club,
        "target": ball_reference.target_for(metric, club),
        "points": [{"shot_id": sid, "captured_at": ts, "value": value}
                   for (sid, ts, value) in rows],
    }
