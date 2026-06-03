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
    return [player_dict(p) for p in repo.list_players(conn)]


@router.post("")
def create_player(body: PlayerIn, conn=Depends(get_conn)):
    p = repo.get_or_create_player(conn, body.name, body.height_in,
                                  body.handedness)
    return player_dict(p)
