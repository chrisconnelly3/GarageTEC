"""Path-traversal-safe media file serving from the media root."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from web.backend.deps import media_root

router = APIRouter(tags=["media"])


@router.get("/media/{path:path}")
def get_media_file(path: str, root: Path = Depends(media_root)):
    root = root.resolve()
    candidate = (root / path).resolve()
    # candidate must live strictly inside root
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(str(candidate))
