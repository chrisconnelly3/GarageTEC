# web/backend/api_calibration.py
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel

from store import repo
from web.backend.deps import (get_conn, get_calibration_supervisor,
                              calibration_bus)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


class StartIn(BaseModel):
    device_index: int = 0
    cols: int = 9
    rows: int = 6
    square_mm: float = 25.0


@router.post("/start")
def start(body: StartIn, sup=Depends(get_calibration_supervisor)):
    sup.start(device_index=body.device_index, cols=body.cols, rows=body.rows,
              square_mm=body.square_mm)
    return {"ok": True}


@router.post("/stop")
def stop(sup=Depends(get_calibration_supervisor)):
    sup.stop(); return {"ok": True}


@router.post("/run")
def run(sup=Depends(get_calibration_supervisor)):
    return sup.run()


@router.get("/status")
def status(sup=Depends(get_calibration_supervisor)):
    return sup.status()


@router.get("/active")
def active(conn=Depends(get_conn)):
    c = repo.get_active_calibration(conn)
    if c is None:
        return None
    return {"id": c.id, "created_at": c.created_at, "n_poses": c.n_poses,
            "reprojection_error": c.reprojection_error,
            "cols": c.cols, "rows": c.rows, "device_index": c.device_index}


@router.get("/history")
def history(conn=Depends(get_conn)):
    return [{"id": c.id, "created_at": c.created_at, "n_poses": c.n_poses,
             "reprojection_error": c.reprojection_error, "is_active": c.is_active}
            for c in repo.list_calibrations(conn)]


@router.post("/activate/{cal_id}")
def activate(cal_id: int, conn=Depends(get_conn)):
    c = repo.set_active_calibration(conn, cal_id)
    return {"ok": c is not None}


@router.get("/export")
def export(conn=Depends(get_conn)):
    c = repo.get_active_calibration(conn)
    if c is None:
        return JSONResponse(status_code=404, content={"error": "no active calibration"})
    return JSONResponse(content=json.loads(c.calib_json),
                        headers={"Content-Disposition": "attachment; filename=bay_calib.json"})


def _sse(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@router.get("/stream")
async def stream(request: Request, bus=Depends(calibration_bus)):
    async def gen():
        while True:
            if await request.is_disconnected():
                break
            for e in bus.drain():
                yield _sse(e["event"], e["data"])
            yield ": keep-alive\n\n"
            await asyncio.sleep(0.4)
    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/preview")
async def preview(sup=Depends(get_calibration_supervisor)):
    boundary = "frame"

    async def gen():
        for _ in range(100000):                     # bounded; client disconnects end it
            jpeg = sup.latest_overlay_jpeg()
            if jpeg:
                yield (b"--" + boundary.encode() + b"\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n")
            await asyncio.sleep(0.033)              # ~30 fps target; async so client close cancels

    return StreamingResponse(
        gen(), media_type=f"multipart/x-mixed-replace; boundary={boundary}")
