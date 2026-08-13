# web/backend/api_calibration.py
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse, JSONResponse, Response
from pydantic import BaseModel

from store import repo
from web.backend.deps import (get_conn, get_calibration_supervisor,
                              calibration_bus)

router = APIRouter(prefix="/api/calibration", tags=["calibration"])


class StartIn(BaseModel):
    device_left: int = 0                # down-the-line camera
    device_right: int | None = None     # face-on camera (None in mono test mode)
    cols: int = 9
    rows: int = 6
    square_mm: float = 25.0
    mono: bool = False                  # single-camera (laptop webcam) test mode


@router.get("/cameras")
def cameras():
    """Connected USB cameras with friendly names, for the device dropdowns."""
    from vision.frames import list_cameras
    return list_cameras()


@router.post("/start")
def start(body: StartIn, sup=Depends(get_calibration_supervisor)):
    sup.start(device_left=body.device_left, device_right=body.device_right,
              cols=body.cols, rows=body.rows, square_mm=body.square_mm,
              mono=body.mono)
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
    from fastapi import HTTPException
    c = repo.set_active_calibration(conn, cal_id)
    if c is None:
        raise HTTPException(status_code=404, detail="calibration not found")
    return {"ok": True}


@router.get("/checkerboard.svg")
def checkerboard(square_mm: float = 25.0, cols: int = 10, rows: int = 7):
    """A print-ready calibration checkerboard, sized in real millimetres.

    Shipping this removes the most common calibration failure: users download an
    arbitrary board off the internet whose square count does not match what the
    app expects, or print it scaled so every measurement is wrong. SVG is used
    rather than PNG because physical `mm` units print at true size.

    `cols`/`rows` are SQUARE counts; OpenCV counts INNER CORNERS, which is one
    less in each direction (10x7 squares -> 9x6 corners, the app's default).
    """
    square_mm = min(max(square_mm, 5.0), 60.0)
    cols = min(max(cols, 3), 20)
    rows = min(max(rows, 3), 20)

    # A white quiet zone around the board is required for reliable corner
    # detection; without it OpenCV can miss the outer row entirely.
    margin = 10.0
    board_w, board_h = cols * square_mm, rows * square_mm
    label_h = 12.0
    w, h = board_w + 2 * margin, board_h + 2 * margin + label_h

    squares = []
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 == 0:
                continue  # leave white
            x = margin + c * square_mm
            y = margin + r * square_mm
            squares.append(
                f'<rect x="{x:.3f}" y="{y:.3f}" width="{square_mm:.3f}" '
                f'height="{square_mm:.3f}" fill="#000"/>')

    inner = f"{cols - 1} x {rows - 1}"
    label_y = margin + board_h + 8.0
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}mm" '
        f'height="{h:.3f}mm" viewBox="0 0 {w:.3f} {h:.3f}">'
        f'<rect width="{w:.3f}" height="{h:.3f}" fill="#fff"/>'
        + "".join(squares)
        + f'<text x="{margin:.3f}" y="{label_y:.3f}" font-family="sans-serif" '
          f'font-size="4" fill="#000">'
          f'GarageTEC calibration board &#8212; {square_mm:g} mm squares, '
          f'{inner} inner corners. Print LANDSCAPE at 100% / Actual Size (NOT '
          f'&#8220;fit to page&#8221;), then measure one square with a ruler and '
          f'enter that number as Square size (mm) in the app.'
        f'</text></svg>'
    )
    return Response(content=svg, media_type="image/svg+xml")


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
