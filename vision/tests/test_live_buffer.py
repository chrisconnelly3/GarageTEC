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


def test_flush_raises_when_writer_not_opened(tmp_path, monkeypatch):
    """Fix 3: if the VideoWriter fails to open (codec unavailable), flush must
    raise rather than silently returning a path to an empty/unreadable file."""
    import vision.live_buffer as lb

    class _DeadWriter:
        def isOpened(self):
            return False

        def write(self, f):
            raise AssertionError("must not write when not opened")

        def release(self):
            pass

    monkeypatch.setattr(lb.cv2, "VideoWriter", lambda *a, **k: _DeadWriter())
    buf = RollingFrameBuffer(fps=20.0, window_s=5.0)
    for i in range(5):
        buf.push(np.zeros((48, 64, 3), np.uint8), time_s=i / 20.0)
    import pytest
    with pytest.raises(RuntimeError):
        buf.flush_to_video(str(tmp_path / "wont_open.mp4"))


def test_push_defaults_to_real_monotonic_time(monkeypatch):
    """Fix 3: push() with no time_s stamps frames on the real monotonic clock,
    so eviction reflects ACTUAL elapsed time (not a synthetic fps clock)."""
    import vision.live_buffer as lb
    clock = {"t": 100.0}
    monkeypatch.setattr(lb.time, "monotonic", lambda: clock["t"])
    buf = RollingFrameBuffer(fps=30.0, window_s=1.0)
    buf.push(np.zeros((4, 4, 3), np.uint8))            # t=100.0
    clock["t"] = 100.5
    buf.push(np.zeros((4, 4, 3), np.uint8))            # t=100.5 (within window)
    clock["t"] = 102.0
    buf.push(np.zeros((4, 4, 3), np.uint8))            # t=102.0 -> evicts older
    assert len(buf) == 1


def test_observed_fps_matches_real_rate():
    """observed_fps() reports the rate implied by the buffered timestamps so a
    real camera rate != configured fps isn't time-distorted in the clip."""
    buf = RollingFrameBuffer(fps=240.0, window_s=100.0)  # nominal fps far off
    # 11 frames spaced 0.1s apart -> 10 intervals over 1.0s -> 10 fps observed.
    for i in range(11):
        buf.push(np.zeros((4, 4, 3), np.uint8), time_s=i * 0.1)
    assert abs(buf.observed_fps() - 10.0) < 1e-6


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
