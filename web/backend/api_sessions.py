from fastapi import APIRouter, Depends, HTTPException

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import session_dict, swing_dict, coaching_dict

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(player: int | None = None, conn=Depends(get_conn)):
    return [session_dict(s) for s in repo.list_sessions(conn, player_id=player)]


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
