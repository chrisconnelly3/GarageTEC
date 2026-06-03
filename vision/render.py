"""Optional: draw a per-swing annotated clip (skeleton dots + phase labels) for
immediate review. Saved as an mp4 the persister records as media. Best-effort
overlay — frames without pose are written through unannotated.
"""
import os
from typing import List, Optional

import cv2

from vision import constants as C
from vision.types import SwingWindow
from store.models import Landmark, Moment

# simple skeleton connections by landmark name
_CONNECTIONS = [
    ("left_shoulder", "right_shoulder"),
    ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"),
    ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"),
    ("left_shoulder", "left_hip"), ("right_shoulder", "right_hip"),
    ("left_hip", "right_hip"),
    ("left_hip", "left_knee"), ("left_knee", "left_ankle"),
    ("right_hip", "right_knee"), ("right_knee", "right_ankle"),
]


def _draw_skeleton(img, landmarks: List[Landmark]):
    by = {lm.name: lm for lm in landmarks}
    for a, b in _CONNECTIONS:
        if a in by and b in by:
            pa = (int(by[a].x), int(by[a].y))
            pb = (int(by[b].x), int(by[b].y))
            cv2.line(img, pa, pb, (0, 255, 0), C.SKELETON_THICKNESS)
    for lm in landmarks:
        cv2.circle(img, (int(lm.x), int(lm.y)), 3, (0, 200, 255), -1)


def render_swing_clip(frames, poses: List[Optional[List[Landmark]]],
                      moments: List[Moment], window: SwingWindow,
                      out_path: str, fps: float = 30.0) -> str:
    """`frames` and `poses` are aligned lists over the swing window (same length).
    Writes an annotated mp4 to out_path and returns out_path.
    """
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    h, w = frames[0].shape[:2]
    fourcc = cv2.VideoWriter_fourcc(*C.RENDER_FOURCC)
    writer = cv2.VideoWriter(out_path, fourcc, fps, (w, h))
    # map absolute frame_index -> phase label for quick lookup
    label_at = {m.frame_index: m.kind for m in moments}
    for offset, img in enumerate(frames):
        canvas = img.copy()
        lms = poses[offset] if offset < len(poses) else None
        if lms:
            _draw_skeleton(canvas, lms)
        abs_idx = window.start_index + offset
        if abs_idx in label_at:
            cv2.putText(canvas, label_at[abs_idx], (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, C.LABEL_FONT_SCALE,
                        (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(canvas)
    writer.release()
    return out_path
