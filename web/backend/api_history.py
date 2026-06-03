from fastapi import APIRouter, Depends

from store import repo
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/history", tags=["history"])


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
