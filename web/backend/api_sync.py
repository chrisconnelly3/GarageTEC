from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from store import repo
from sync.service import SyncService
from web.backend.deps import get_conn
from web.backend.serializers import swing_dict, shot_dict

router = APIRouter(prefix="/api/sync", tags=["sync"])


class ApplyIn(BaseModel):
    swing_id: int
    shot_id: int


class UnlinkIn(BaseModel):
    swing_id: int


def _proposal_dict(p):
    return {"swing_id": p.swing_id, "shot_id": p.shot_id,
            "confidence": p.confidence, "reason": p.reason}


@router.get("/proposals")
def proposals(session: int, conn=Depends(get_conn)):
    service = SyncService(conn)
    swings = repo.list_unmatched_swings(conn, session_id=session)
    shots = repo.list_unmatched_shots(conn, session_id=session)
    players = {sw.player_id for sw in swings} | {sh.player_id for sh in shots}
    props = []
    for player_id in (pid for pid in players if pid is not None):
        props.extend(service.propose_matches(session_id=session,
                                              player_id=player_id))
    props.sort(key=lambda p: p.confidence, reverse=True)
    return {
        "session": session,
        "proposals": [_proposal_dict(p) for p in props],
        "unmatched_swings": [swing_dict(sw) for sw in swings],
        "unmatched_shots": [shot_dict(sh) for sh in shots],
    }


@router.post("/apply")
def apply(body: ApplyIn, conn=Depends(get_conn)):
    if repo.get_swing(conn, body.swing_id) is None:
        raise HTTPException(status_code=404, detail="swing not found")
    if repo.get_shot(conn, body.shot_id) is None:
        raise HTTPException(status_code=404, detail="shot not found")
    SyncService(conn).apply_match(swing_id=body.swing_id, shot_id=body.shot_id)
    return {"ok": True}


@router.post("/unlink")
def unlink(body: UnlinkIn, conn=Depends(get_conn)):
    if repo.get_swing(conn, body.swing_id) is None:
        raise HTTPException(status_code=404, detail="swing not found")
    SyncService(conn).unlink(swing_id=body.swing_id)
    return {"ok": True}
