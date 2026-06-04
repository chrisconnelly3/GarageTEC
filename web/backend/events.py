"""SSE stream + store-polling watcher for newly-ready swings.

A swing is READY when it has at least one metric AND at least one coaching
row. The watcher remembers the highest swing id it has emitted and only
returns newly-ready swings with a larger id, so each ready swing fires once.

The stream also drains the in-process CaptureEventBus, emitting capture frames
(shot_received, capture_status, active_player_changed) alongside swing_ready.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from web.backend.deps import get_conn, capture_bus

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


def _format(event_name: str, data: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(data)}\n\n"


@router.get("/events")
async def events(request: Request, once: int = 0, conn=Depends(get_conn),
                 bus=Depends(capture_bus)):
    watcher = SwingWatcher(conn)

    def _emit_capture():
        return [_format(e["event"], e["data"]) for e in bus.drain()]

    async def gen():
        for e in watcher.poll():
            yield _format("swing_ready", e)
        for frame in _emit_capture():
            yield frame
        if once:
            return
        while True:
            if await request.is_disconnected():
                break
            for e in watcher.poll():
                yield _format("swing_ready", e)
            for frame in _emit_capture():
                yield frame
            yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_S)

    return StreamingResponse(gen(), media_type="text/event-stream")
