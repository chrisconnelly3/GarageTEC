"""Time-bounded rolling frame buffer for live swing capture.

Frames are pushed in (from any source exposing ``read_composite()`` — a live
camera, a dual-camera composite, or a fake/video source in tests) with a
timestamp; the buffer keeps only the last ``window_s`` seconds. ``flush_to_video``
dumps the current buffer to a temp ``.mp4`` (cv2.VideoWriter) so the existing
``process_video`` pipeline can run on the recorded clip.

Hardware-agnostic: nothing here opens a device. The capture supervisor owns the
device; this just stores frames and writes them out.
"""
import time
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

    def push(self, frame, *, time_s: Optional[float] = None):
        """Append a BGR frame and evict stale frames.

        ``time_s`` is the frame's capture timestamp; if omitted it defaults to
        the real wall clock (``time.monotonic()``). Stamping with real time means
        the eviction window reflects the ACTUAL elapsed time, so the retained
        clip is ``window_s`` real seconds even when the camera's real frame rate
        differs from the configured ``fps``.
        """
        if frame is None:
            return
        if self.width is None:
            h, w = frame.shape[:2]
            self.width, self.height = int(w), int(h)
        t = time.monotonic() if time_s is None else float(time_s)
        self._frames.append((t, frame))
        self._evict(now_s=t)

    def _evict(self, *, now_s: float):
        cutoff = now_s - self.window_s
        while self._frames and self._frames[0][0] < cutoff:
            self._frames.popleft()

    def snapshot(self):
        """Return the buffered frames (oldest -> newest) as a list."""
        return [f for _, f in self._frames]

    def fill_from_source(self, source, *, max_frames: Optional[int] = None,
                         real_time: bool = False) -> int:
        """Pull frames from a source via read_composite() into the buffer. Stops
        at exhaustion (None) or max_frames. Returns the number of frames read.

        ``real_time=False`` (default) stamps frames on a synthetic ``fps``-based
        clock -- correct for deterministic tests and offline video where one
        read == one frame interval. ``real_time=True`` stamps each frame with the
        real wall clock (``time.monotonic()``) so a LIVE camera whose true rate
        differs from the configured ``fps`` is not time-distorted; eviction then
        reflects actual elapsed time. Used by tests and the warm-up path."""
        read = 0
        base = self._frames[-1][0] if self._frames else 0.0
        while max_frames is None or read < max_frames:
            frame = source.read_composite()
            if frame is None:
                break
            read += 1
            if real_time:
                self.push(frame)                       # real monotonic stamp
            else:
                self.push(frame, time_s=base + read / self.fps)
        return read

    def observed_fps(self) -> Optional[float]:
        """Effective frame rate implied by the buffered timestamps (frames per
        real second across the buffered span), or None if too few frames to
        measure. Lets the writer match the real capture rate instead of the
        nominal ``fps`` when the buffer was filled with real-time stamps."""
        if len(self._frames) < 2:
            return None
        span = self._frames[-1][0] - self._frames[0][0]
        if span <= 0.0:
            return None
        # (n-1) intervals over the span.
        return (len(self._frames) - 1) / span

    def flush_to_video(self, path: str) -> Optional[str]:
        """Write the current buffer to ``path`` as an mp4 and return the path.
        Returns None if the buffer is empty (nothing to write). Raises
        RuntimeError if the VideoWriter could not be opened (e.g. the mp4v codec
        is unavailable), so callers don't get a path to an empty/invalid file."""
        frames = self.snapshot()
        if not frames:
            return None
        h, w = frames[0].shape[:2]
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        # Prefer the real observed rate so the clip plays at true speed; fall
        # back to the configured fps when the buffer can't measure a rate.
        write_fps = self.observed_fps() or self.fps
        writer = cv2.VideoWriter(path, fourcc, write_fps, (w, h))
        if not writer.isOpened():
            # Codec unavailable -> the writer would silently drop every frame and
            # leave a 0-byte/unreadable file. Fail loudly instead.
            writer.release()
            raise RuntimeError(
                f"could not open VideoWriter for {path!r} (codec 'mp4v' "
                f"unavailable?); no video written")
        try:
            for f in frames:
                if f.shape[:2] != (h, w):
                    f = cv2.resize(f, (w, h))
                writer.write(f)
        finally:
            writer.release()
        return path
