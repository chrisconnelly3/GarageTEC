"""Orchestrate the whole rock: frames -> pose(both views, cached) -> swing_detect
-> for each swing(segment -> persist -> optional render). Emits one SwingResult
per swing via the `on_swing` callback as soon as the swing is persisted, so a
future live source yields per-swing data immediately (the spec's immediacy goal).
"""
import os
from datetime import datetime
from typing import Callable, List, Optional, Tuple

from vision import constants as C
from vision.frames import VideoFileSource, FrameSource
from vision.pose import make_pose_estimator
from vision.swing_detect import hand_trajectory_from_timeline, detect_swings
from vision.segment import segment_swing
from vision.persist import persist_swing
from vision.render import render_swing_clip
from vision.threed.pipeline3d import reconstruct_window
from vision.types import PoseTimeline, SwingResult


def build_timelines(source: FrameSource, dl_pose, fo_pose):
    """Run pose once per frame per view; return (down_line, face_on) timelines.
    Also caches the raw face_on crops keyed by frame index for optional render.
    """
    down_line = PoseTimeline(view=C.VIEW_DOWN_LINE)
    face_on = PoseTimeline(view=C.VIEW_FACE_ON)
    crops_cache = {}
    for sample in source.frames():
        dl_crop = sample.view_crops[C.VIEW_DOWN_LINE]
        fo_crop = sample.view_crops[C.VIEW_FACE_ON]
        down_line.times_s.append(sample.time_s)
        face_on.times_s.append(sample.time_s)
        down_line.frames.append(dl_pose.estimate(dl_crop))
        face_on.frames.append(fo_pose.estimate(fo_crop))
        crops_cache[sample.index] = fo_crop
    build_timelines.last_crops = crops_cache  # attribute stash for render reuse
    return down_line, face_on


def process_video(conn, video_path: str, *, player_id: int, session_id: int,
                  split: float = C.DEFAULT_SPLIT, single_swing: bool = False,
                  render: bool = False, out_dir: str = "swings",
                  on_swing: Optional[Callable[[SwingResult], None]] = None,
                  calibration=None, pose_backend: Optional[str] = None
                  ) -> List[SwingResult]:
    """Process a recorded video end to end. Returns the list of SwingResults
    (also delivered one-by-one via on_swing as each swing is persisted).
    pose_backend overrides constants.POSE_BACKEND ("mediapipe"|"rtmpose")."""
    source = VideoFileSource(video_path, split=split)
    dl_pose = make_pose_estimator(C.VIEW_DOWN_LINE, pose_backend)
    fo_pose = make_pose_estimator(C.VIEW_FACE_ON, pose_backend)
    results: List[SwingResult] = []
    try:
        down_line, face_on = build_timelines(source, dl_pose, fo_pose)
        crops_cache = getattr(build_timelines, "last_crops", {})

        signal = hand_trajectory_from_timeline(face_on)
        windows = detect_swings(signal, single_swing=single_swing)
        print(f"[vision] detected {len(windows)} swing(s) in {video_path}")

        for wi, window in enumerate(windows):
            print(f"[vision]   swing {wi}: frames "
                  f"[{window.start_index},{window.end_index}]")
            moments = segment_swing(down_line, face_on, window)

            annotated_path = None
            if render:
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                annotated_path = os.path.join(
                    out_dir, f"{stamp}_swing{wi}", "annotated.mp4")
                frames = [crops_cache[i] for i in
                          range(window.start_index, window.end_index + 1)
                          if i in crops_cache]
                poses = [face_on.frames[i] for i in
                         range(window.start_index, window.end_index + 1)
                         if i in crops_cache]
                if frames:
                    render_swing_clip(frames, poses, moments, window,
                                      annotated_path, fps=source.fps)
                else:
                    annotated_path = None

            swing_id = persist_swing(
                conn, player_id=player_id, session_id=session_id,
                source_video_path=video_path, fps=source.fps,
                width=source.width, height=source.height,
                view_layout=C.VIEW_LAYOUT, down_line=down_line, face_on=face_on,
                window=window, moments=moments, annotated_path=annotated_path)

            if calibration is None:
                from vision.threed.calibration import active_calibration
                # The landmarks fed to reconstruct() are in PER-VIEW (half-crop)
                # pixel coords from split_views(), NOT the full composite width.
                # split_views splits at x = round(W * split): down_line = [:, :x]
                # (width x), face_on = [:, x:] (width W - x). The AssumedGeometry
                # fallback builds one K (cx/focal) that must match that half-view
                # frame, so pass the face-on half width here, not source.width.
                split_x = int(round(source.width * split))
                view_width = source.width - split_x   # face_on (right) crop width
                view_height = source.height
                calibration = active_calibration(conn, image_width=view_width,
                                                 image_height=view_height)
            if calibration is not None:
                frames_3d = reconstruct_window(
                    face_on, down_line, calibration,
                    window.start_index, window.end_index)
                if frames_3d:
                    from store import repo
                    repo.save_pose_3d_frames(conn, swing_id, frames_3d)

            media_paths = [video_path] + (
                [annotated_path] if annotated_path else [])
            result = SwingResult(
                swing_id=swing_id, moments=moments,
                frame_range=(window.start_index, window.end_index),
                view_layout=C.VIEW_LAYOUT, media_paths=media_paths)
            results.append(result)
            if on_swing is not None:
                on_swing(result)
    finally:
        source.close()
        dl_pose.close()
        fo_pose.close()
    return results
