import os
import numpy as np
from vision.render import render_swing_clip
from vision.types import SwingWindow
from vision import constants as C
from store.models import Landmark, Moment


def _frames(n, h=120, w=160):
    return [np.full((h, w, 3), 30, dtype=np.uint8) for _ in range(n)]


def _pose_list(n):
    out = []
    for i in range(n):
        out.append([
            Landmark("left_shoulder", 40.0, 30.0, 0.0, 0.9),
            Landmark("left_wrist", 40.0 + i, 60.0, 0.0, 0.9),
            Landmark("left_hip", 42.0, 80.0, 0.0, 0.9),
        ])
    return out


def test_render_writes_nonempty_mp4(tmp_path):
    n = 20
    frames = _frames(n)
    poses = _pose_list(n)
    window = SwingWindow(0, n - 1, 10)
    moments = [Moment(swing_id=1, kind="address", view="face_on",
                      frame_index=0, time_s=0.0),
               Moment(swing_id=1, kind="impact", view="face_on",
                      frame_index=14, time_s=0.46)]
    out = os.path.join(str(tmp_path), "annotated.mp4")
    path = render_swing_clip(frames, poses, moments, window, out, fps=30.0)
    assert path == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0


def test_render_handles_missing_pose_frames(tmp_path):
    n = 10
    frames = _frames(n)
    poses = [None] * n          # no pose anywhere
    window = SwingWindow(0, n - 1, 5)
    out = os.path.join(str(tmp_path), "a.mp4")
    path = render_swing_clip(frames, poses, [], window, out, fps=30.0)
    assert os.path.exists(path) and os.path.getsize(path) > 0
