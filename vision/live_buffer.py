"""Time-bounded rolling frame buffer for live swing capture.

Frames are pushed in (from any source exposing ``read_composite()`` — a live
camera, a dual-camera composite, or a fake/video source in tests) with a
timestamp; the buffer keeps only the last ``window_s`` seconds. ``flush_to_video``
dumps the current buffer to a temp ``.mp4`` (cv2.VideoWriter) so the existing
``process_video`` pipeline can run on the recorded clip.

Hardware-agnostic: nothing here opens a device. The capture supervisor owns the
device; this just stores frames and writes them out.
"""
from collections import deque
from typing import Optional

import cv2


class RollingFrameBuffer:
    """A deque of (time_s, frame) bounded to the last ``window_s`` seconds.

    fps + window_s are configurable. Eviction is by timestamp: any frame older
    than ``newest - window_s`` is dropped. ``maxlen`` (fps * window_s, padded)
    caps memory even if timestamps misbehave.
    """

    def __init__(self, *, fps: float = 30.0, window_s: float = 3.0):
        self.fps = float(fps) or 30.0
        self.window_s = float(window_s)
        # Hard size cap so a runaway clock can't grow the buffer unbounded.
        cap = int(self.fps * self.window_s) + 2
        self._frames = deque(maxlen=max(cap, 1))
        self.width: Optional[int] = None
        self.height: Optional[int] = None

    def __len__(self):
        return len(self._frames)

    def clear(self):
        self._frames.clear()

    def push(self, frame, *, time_s: float):
        """Append a BGR frame stamped at ``time_s`` and evict stale frames."""
        if frame is None:
            return
        if self.width is None:
            h, w = frame.shape[:2]
            self.width, self.height = int(w), int(h)
        self._frames.append((float(time_s), frame))
        self._evict(now_s=float(time_s))

    def _evict(self, *, now_s: float):
        cutoff = now_s - self.window_s
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()

    def snapshot(self):
        """Return the buffered frames (oldest -> newest) as a list."""
        return [f for _, f in self._frames]

    def fill_from_source(self, source, *, max_frames: Optional[int] = None) -> int:
        """Pull frames from a source via read_composite() into the buffer using a
        synthetic fps-based clock. Stops at exhaustion (None) or max_frames.
        Returns the number of frames read. Used by tests and the warm-up path."""
        read = 0
        base = self._frames[-1][0] if self._frames else 0.0
        while max_frames is None or read < max_frames:
            frame = source.read_composite()
            if frame is None:
                break
            read += 1
            self.push(frame, time_s=base + read / self.fps)
        return read

    def flush_to_video(self, path: str) -> Optional[str]:
        """Write the current buffer to ``path`` as an mp4 and return the path.
        Returns None if the buffer is empty (nothing to write)."""
        frames = self.snapshot()
        if not frames:
            return None
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(path, fourcc, self.fps, (w, h))
        try:
            for f in frames:
                if f.shape[:2] != (h, w):
                    f = cv2.resize(f, (w, h))
                writer.write(f)
        finally:
            writer.release()
        return path
