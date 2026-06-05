# web/backend/api_live_capture.py
"""REST + SSE for live swing capture (rolling-buffer auto-trigger engine).

start/stop control the capture thread + camera source; status reports the
buffer/source state; the SSE stream relays live_capture_status and
live_swing_captured events to the frontend.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from web.backend.deps import get_live_capture_supervisor, live_capture_bus

router = APIRouter(prefix="/api/live-capture", tags=["live-capture"])


class StartIn(BaseModel):
    device_left: int = 0                # down-the-line camera
    device_right: int | None = None     # face-on camera (None = single/mono)
    mono: bool = False                  # single-camera test mode
    fps: float | None = None
    window_s: float | None = None       # rolling buffer length (seconds)
    post_shot_delay_s: float | None = None


@router.post("/start")
def start(body: StartIn, sup=Depends(get_live_capture_supervisor)):
    sup.start(device_left=body.device_left, device_right=body.device_right,
              mono=body.mono, fps=body.fps, window_s=body.window_s,
              post_shot_delay_s=body.post_shot_delay_s)
    return sup.status()


@router.post("/stop")
def stop(sup=Depends(get_live_capture_supervisor)):
    sup.stop()
    return sup.status()


@router.get("/status")
def status(sup=Depends(get_live_capture_supervisor)):
    return sup.status()


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(request: Request, bus=Depends(live_capture_bus)):
    async def gen():
        while True:
            if await request.is_disconnected():
                break
            for e in bus.drain():
                yield _sse(e["event"], e["data"])
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)
    return StreamingResponse(gen(), media_type="text/event-stream")
