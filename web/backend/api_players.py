from fastapi import APIRouter, Depends
from pydantic import BaseModel

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import player_dict

router = APIRouter(prefix="/api/players", tags=["players"])


class PlayerIn(BaseModel):
    name: str
    height_in: float
    handedness: str


@router.get("")
def list_players(conn=Depends(get_conn)):
    out = []
    for p in repo.list_players(conn):
        d = player_dict(p)
        d["swing_count"] = repo.count_swings_for_player(conn, p.id)
        d["session_count"] = repo.count_sessions_for_player(conn, p.id)
        out.append(d)
    return out


@router.post("")
def create_player(body: PlayerIn, conn=Depends(get_conn)):
    p = repo.get_or_create_player(conn, body.name, body.height_in,
                                  body.handedness)
    return player_dict(p)
