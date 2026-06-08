from fastapi import APIRouter, Depends, HTTPException

from store import repo
from coach import ball_reference, golftec
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/history", tags=["history"])

# Separate router for the ball-metric trend endpoint (different path prefix).
ball_router = APIRouter(prefix="/api/ball-history", tags=["history"])

# Body-metric allowlist: the real metric names that are valid for swing_history
# queries (guards against arbitrary input, not SQL injection — the query is
# parameterized). This is the set the UI requests (frontend BODY_CARD_ORDER);
# keep it in sync when adding/renaming body metrics.
BODY_METRICS = {
    "shoulder_tilt_deg", "hip_tilt_deg", "spine_angle_deg",
    "shoulder_turn_deg", "hip_turn_deg",
    "x_factor_deg", "x_factor_stretch_deg",
    "hip_sway_in", "head_sway_in", "early_extension_in", "hand_depth_in",
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
    # Tour-pro reference value for this (metric, context), from the same GolfTEC
    # reference the swing "vs Tour Pro" panel uses. None when no target exists
    # (e.g. raw metrics, or the "overall" context which has no phase target).
    target = golftec.compare(metric, context, 0.0).get("target")
    return {
        "player": player,
        "metric": metric,
        "context": context,
        "target": target,
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
