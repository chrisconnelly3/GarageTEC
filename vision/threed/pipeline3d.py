"""Glue between the per-swing frame window and the 3D reconstructor: reconstruct
only the swing's frames and key them by absolute composite frame index (so they
align with the moments the metrics read)."""
from typing import Dict, List

from store.models import Landmark3D
from vision.threed.reconstruct import reconstruct


def reconstruct_window(face_on, down_line, calibration,
                       start_index: int, end_index: int) -> Dict[int, List[Landmark3D]]:
    """Triangulate frames [start_index, end_index] (inclusive) and return
    {absolute_frame_index: [Landmark3D]}. Empty 3D frames are skipped."""
    tl = reconstruct(face_on, down_line, calibration)
    out: Dict[int, List[Landmark3D]] = {}
    for idx in range(start_index, min(end_index, len(tl) - 1) + 1):
        lms = tl.frames[idx] if idx < len(tl.frames) else None
        if lms:
            out[idx] = lms
    return out
