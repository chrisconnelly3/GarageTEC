"""SSE stream + store-polling watcher for newly-ready swings.

A swing is READY when it has at least one metric AND at least one coaching
row. The watcher remembers the highest swing id it has emitted and only
returns newly-ready swings with a larger id, so each ready swing fires once.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from web.backend.deps import get_conn

router = APIRouter(tags=["events"])

POLL_INTERVAL_S = 1.5

_READY_SQL = """
SELECT sw.id AS swing_id, sw.session_id, sw.player_id
FROM swing sw
WHERE sw.id > ?
  AND EXISTS (SELECT 1 FROM metric m WHERE m.swing_id = sw.id)
  AND EXISTS (SELECT 1 FROM coaching c WHERE c.swing_id = sw.id)
ORDER BY sw.id
"""


class SwingWatcher:
    def __init__(self, conn, last_id: int = 0):
        self.conn = conn
        self.last_id = last_id

    def poll(self):
        rows = self.conn.execute(_READY_SQL, (self.last_id,)).fetchall()
        events = []
        for r in rows:
            self.last_id = max(self.last_id, r["swing_id"])
            events.append({"swing_id": r["swing_id"],
                           "session_id": r["session_id"],
                           "player_id": r["player_id"]})
        return events


def _format(event: dict) -> str:
    return f"event: swing_ready\ndata: {json.dumps(event)}\n\n"


@router.get("/events")
async def events(request: Request, once: int = 0, conn=Depends(get_conn)):
    watcher = SwingWatcher(conn)

    async def gen():
        # emit any already-ready swings immediately
        for e in watcher.poll():
            yield _format(e)
        if once:
            return
        while True:
            if await request.is_disconnected():
                break
            for e in watcher.poll():
                yield _format(e)
            yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_S)

    return StreamingResponse(gen(), media_type="text/event-stream")
