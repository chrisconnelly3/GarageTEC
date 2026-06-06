from fastapi import APIRouter, Depends, HTTPException

from store import repo
from coach import ball_reference
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/history", tags=["history"])

# Separate router for the ball-metric trend endpoint (different path prefix).
ball_router = APIRouter(prefix="/api/ball-history", tags=["history"])

# Body-metric allowlist: the set of metric names that are valid for
# swing_history queries (not arbitrary SQL injection). Add new names here as
# GolfTEC metrics expand.
BODY_METRICS = {
    "hip_sway_in", "shoulder_tilt_deg", "hip_rotation_deg",
    "shoulder_rotation_deg", "tempo", "spine_angle_deg", "weight_transfer",
    "wrist_angle_deg", "elbow_angle_deg", "knee_flex_deg",
}

VALID_CONTEXTS = {"address", "top", "impact", "finish", "overall"}


@router.get("")
def history(player: int, metric: str, context: str = "overall",
            conn=Depends(get_conn)):
    if metric not in BODY_METRICS:
        raise HTTPException(status_code=400,
                            detail=f"unknown body metric: {metric!r}")
    if context not in VALID_CONTEXTS:
        raise HTTPException(status_code=400,
                            detail=f"invalid context: {context!r}")
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
