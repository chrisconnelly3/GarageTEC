from fastapi import APIRouter, Depends, HTTPException

from store import repo
from coach import golftec, ball_reference
from web.backend.deps import get_conn
from web.backend.serializers import (
    session_dict, swing_dict, coaching_dict, metric_dict, shot_dict,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(player: int | None = None, conn=Depends(get_conn)):
    return [session_dict(s) for s in repo.list_sessions(conn, player_id=player)]


@router.get("/{session_id}/stats")
def session_stats(session_id: int, conn=Depends(get_conn)):
    """At-a-glance card data for the Sessions list: club mix, the session's
    headline ball number, how many benchmarked metrics landed in tour range, the
    latest swing to deep-link into, and the AI session takeaway when one exists.
    All numbers are computed from stored swings/shots/benchmarks (nothing made up)."""
    session = repo.get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    swings = repo.list_swings(conn, session_id=session_id)

    club_counts: dict[str, int] = {}
    best_carry: float | None = None
    in_range = 0
    total_benchmarked = 0

    for sw in swings:
        if sw.club:
            club_counts[sw.club] = club_counts.get(sw.club, 0) + 1
        # Body metrics vs Tour Pro (only rows with a real zone count toward range).
        metrics = [metric_dict(m) for m in repo.get_metrics(conn, sw.id)]
        for row in golftec.benchmark_metrics(metrics):
            if row.get("zone"):
                total_benchmarked += 1
                in_range += row["zone"] == "green"
        # Ball metrics vs TrackMan tour average.
        if sw.shot_id:
            shot = repo.get_shot(conn, sw.shot_id)
            if shot is not None:
                sd = shot_dict(shot)
                for row in ball_reference.benchmark_ball(sd, shot.club):
                    if row.get("zone"):
                        total_benchmarked += 1
                        in_range += row["zone"] == "green"
                if sd.get("carry") is not None:
                    best_carry = max(best_carry or 0.0, sd["carry"])

    latest = max(swings, key=lambda s: s.created_at, default=None)

    # AI session takeaway (kind="session"), shown only when actually generated.
    takeaway = None
    for c in repo.get_coaching(conn, session_id=session_id):
        cd = coaching_dict(c)
        if cd["kind"] == "session" and cd["content"]:
            takeaway = cd["content"].get("headline")
            break

    return {
        "session_id": session_id,
        "swing_count": len(swings),
        "club_counts": club_counts,
        "top_ball": (
            {"label": "Longest carry", "value": round(best_carry), "unit": "yds"}
            if best_carry is not None else None
        ),
        "tour_range": (
            {"in_range": in_range, "total": total_benchmarked}
            if total_benchmarked else None
        ),
        "latest_swing_id": latest.id if latest else None,
        "takeaway": takeaway,
    }


@router.get("/{session_id}")
def get_session(session_id: int, conn=Depends(get_conn)):
    session = repo.get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    swings = repo.list_swings(conn, session_id=session_id)
    coaching = repo.get_coaching(conn, session_id=session_id)
    return {
        "session": session_dict(session),
        "swings": [swing_dict(sw) for sw in swings],
        "coaching": [coaching_dict(c) for c in coaching],
    }
