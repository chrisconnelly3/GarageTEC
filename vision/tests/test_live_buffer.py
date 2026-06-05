"""Rolling frame buffer tests: time-bounded eviction + flush-to-video.

No hardware: a FakeSource yields synthetic BGR frames via read_composite().
"""
import numpy as np
import cv2

from vision.live_buffer import RollingFrameBuffer


class FakeSource:
    """Stand-in for LiveCameraSource/DualCameraSource: read_composite() returns
    a synthetic solid-colour BGR frame each call, then None when exhausted."""

    def __init__(self, n, width=64, height=48):
        self._frames = [
            np.full((height, width, 3), i % 256, np.uint8) for i in range(n)
        ]
        self._i = 0
        self.width = width
        self.height = height
        self.closed = False

    def read_composite(self):
        if self._i >= len(self._frames):
            return None
        f = self._frames[self._i]
        self._i += 1
        return f

    def close(self):
        self.closed = True


def test_push_keeps_only_window_seconds():
    # 10 fps, 2s window -> at most 20 frames retained.
    buf = RollingFrameBuffer(fps=10.0, window_s=2.0)
    for i in range(50):
        buf.push(np.zeros((4, 4, 3), np.uint8), time_s=i / 10.0)
    assert len(buf) <= 20
    # the retained frames are the most recent ones (eviction by time)
    assert len(buf) == 20


def test_push_evicts_by_wall_time_gaps():
    # frames arriving with real timestamps: only those within window_s of the
    # newest survive, regardless of count.
    buf = RollingFrameBuffer(fps=30.0, window_s=1.0)
    buf.push(np.zeros((4, 4, 3), np.uint8), time_s=0.0)
    buf.push(np.zeros((4, 4, 3), np.uint8), time_s=0.5)
    buf.push(np.zeros((4, 4, 3), np.uint8), time_s=2.0)  # newest; window=[1.0,2.0]
    assert len(buf) == 1


def test_flush_writes_readable_mp4(tmp_path):
    buf = RollingFrameBuffer(fps=20.0, window_s=5.0)
    for i in range(30):
        frame = np.full((48, 64, 3), (i * 8) % 256, np.uint8)
        buf.push(frame, time_s=i / 20.0)
    out = buf.flush_to_video(str(tmp_path / "clip.mp4"))
    assert out is not None
    cap = cv2.VideoCapture(out)
    assert cap.isOpened()
    count = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        count += 1
    cap.release()
    assert count == 30


def test_flush_empty_returns_none(tmp_path):
    buf = RollingFrameBuffer(fps=20.0, window_s=5.0)
    assert buf.flush_to_video(str(tmp_path / "empty.mp4")) is None


def test_fill_from_source_reads_until_exhausted():
    buf = RollingFrameBuffer(fps=10.0, window_s=100.0)
    src = FakeSource(n=5)
    n = buf.fill_from_source(src, max_frames=5)
    assert n == 5
    assert len(buf) == 5


def test_dimensions_inferred_from_first_frame(tmp_path):
    buf = RollingFrameBuffer(fps=15.0, window_s=5.0)
    buf.push(np.zeros((48, 64, 3), np.uint8), time_s=0.0)
    assert buf.width == 64 and buf.height == 48
