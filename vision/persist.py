"""Persist ONE detected swing to the Batch 0 store: a swing row, pose_frames for
both views (sliced to the swing window), the 8 moments, and media references
(always the source video; optionally an annotated clip).
"""
from typing import List, Optional

from vision import constants as C
from vision.types import PoseTimeline, SwingWindow
from store import repo
from store.models import PoseFrame, Media, Moment


def _window_pose_frames(swing_id: int, timeline: PoseTimeline,
                        window: SwingWindow) -> List[PoseFrame]:
    frames = []
    e = min(window.end_index, len(timeline) - 1)
    for i in range(window.start_index, e + 1):
        lms = timeline.frames[i]
        if lms is None:
            continue   # skip frames with no pose; the index gap is acceptable
        frames.append(PoseFrame(
            swing_id=swing_id, view=timeline.view, frame_index=i,
            time_s=timeline.times_s[i], landmarks=lms,
            source="mediapipe_pose"))
    return frames


def persist_swing(conn, *, player_id: int, session_id: int,
                  source_video_path: str, fps: float, width: int, height: int,
                  view_layout: str, down_line: PoseTimeline,
                  face_on: PoseTimeline, window: SwingWindow,
                  moments: List[Moment], club: Optional[str] = None,
                  annotated_path: Optional[str] = None) -> int:
    """Write the swing and all its child rows. Returns the new swing id."""
    swing = repo.add_swing(
        conn, session_id, player_id, source_video_path,
        view_layout=view_layout, fps=fps, width=width, height=height, club=club,
        notes=f"frames[{window.start_index}:{window.end_index}]")
    swing_id = swing.id

    dl_frames = _window_pose_frames(swing_id, down_line, window)
    fo_frames = _window_pose_frames(swing_id, face_on, window)
    if dl_frames:
        repo.save_pose_frames(conn, swing_id, C.VIEW_DOWN_LINE, dl_frames)
    if fo_frames:
        repo.save_pose_frames(conn, swing_id, C.VIEW_FACE_ON, fo_frames)

    # stamp swing_id onto the moments (segment leaves it None)
    for m in moments:
        m.swing_id = swing_id
    repo.save_moments(conn, swing_id, moments)

    # media: always record the source video; optionally the annotated clip
    repo.save_media(conn, Media(swing_id=swing_id, kind="source_video",
                                path=source_video_path))
    if annotated_path:
        repo.save_media(conn, Media(swing_id=swing_id, kind="annotated_video",
                                    path=annotated_path))
    return swing_id
