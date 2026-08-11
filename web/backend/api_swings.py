import json

from fastapi import APIRouter, Depends, HTTPException, Response

from catcher import trust as trust_mod
from store import repo
from coach import golftec, ball_reference
from web.backend.deps import get_conn
from web.backend.serializers import (
    swing_dict, metric_dict, moment_dict, shot_dict, coaching_dict, media_dict,
)

router = APIRouter(prefix="/api/swings", tags=["swings"])


def _swing_detail(conn, swing, shot):
    metrics = [metric_dict(m) for m in repo.get_metrics(conn, swing.id)]
    shot_d = shot_dict(shot)
    return {
        "swing": swing_dict(swing),
        "metrics": metrics,
        "benchmarks": golftec.benchmark_metrics(metrics),   # body vs tour pro
        "shot": shot_d,
        "ball_benchmarks": ball_reference.benchmark_ball(   # ball vs TrackMan
            shot_d, shot.club if shot else None),
        "ball_raw": ball_reference.raw_ball_fields(shot_d),  # raw, un-benchmarked
        "trust": trust_mod.derive_tiers(
            json.loads(shot.enrichment_json)
            if shot is not None and shot.enrichment_json else None
        ),

        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing.id)],
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing.id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing.id)],
    }


_MAX_LIMIT = 200


@router.get("")
def list_swings(player: int | None = None, session: int | None = None,
                limit: int = 50, conn=Depends(get_conn)):
    limit = min(max(1, limit), _MAX_LIMIT)
    return repo.list_swing_summaries(conn, player_id=player,
                                     session_id=session, limit=limit)


@router.get("/latest")
def latest_swing(player: int, session: int | None = None,
                 conn=Depends(get_conn)):
    swing = repo.latest_ready_swing(conn, player, session_id=session)
    if swing is None:
        return Response(status_code=204)
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return _swing_detail(conn, swing, shot)


@router.get("/{swing_id}")
def get_swing(swing_id: int, conn=Depends(get_conn)):
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise HTTPException(status_code=404, detail="swing not found")
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return _swing_detail(conn, swing, shot)
