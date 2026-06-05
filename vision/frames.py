"""Frame source abstraction. VideoFileSource reads a recorded file and yields
per-frame view crops. A future LiveCameraSource implements the same interface
(`frames()` generator of FrameSample), so the rest of the pipeline is unchanged.
"""
import abc
from typing import Dict, Iterator

import cv2

from vision import constants as C
from vision.types import FrameSample


def split_views(frame, split: float = C.DEFAULT_SPLIT) -> Dict[str, object]:
    """Split a side-by-side frame into {down_line: left, face_on: right}."""
    h, w = frame.shape[:2]
    x = int(round(w * split))
    return {
        C.VIEW_DOWN_LINE: frame[:, :x].copy(),
        C.VIEW_FACE_ON: frame[:, x:].copy(),
    }


class FrameSource(abc.ABC):
    """Common interface for recorded and (future) live sources."""

    width: int
    height: int
    fps: float

    @abc.abstractmethod
    def frames(self) -> Iterator[FrameSample]:
        ...

    @abc.abstractmethod
    def close(self) -> None:
        ...


class VideoFileSource(FrameSource):
    def __init__(self, path: str, split: float = C.DEFAULT_SPLIT):
        self.path = path
        self.split = split
        self._cap = cv2.VideoCapture(path)
        if not self._cap.isOpened():
            raise FileNotFoundError(f"could not open video: {path}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0
        self.frame_count = int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))

    def frames(self) -> Iterator[FrameSample]:
        index = 0
        while True:
            ok, frame = self._cap.read()
            if not ok:
                break
            time_s = index / self.fps
            yield FrameSample(index=index, time_s=time_s,
                              view_crops=split_views(frame, self.split))
            index += 1

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class LiveCameraSource(FrameSource):
    """Live capture device (the bay's synced side-by-side composite as a video
    device). First live FrameSource; foundation for live swing capture too.
    `cap_factory` is injectable so tests pass a fake (no real device opened)."""

    def __init__(self, device_index: int = 0, split: float = C.DEFAULT_SPLIT,
                 max_frames=None, cap_factory=None):
        self.device_index = device_index
        self.split = split
        self._max = max_frames
        factory = cap_factory or (lambda i: cv2.VideoCapture(i))
        self._cap = factory(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"could not open camera device {device_index}")
        self.width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = float(self._cap.get(cv2.CAP_PROP_FPS)) or 30.0

    def frames(self) -> Iterator[FrameSample]:
        i = 0
        while self._max is None or i < self._max:
            ok, frame = self._cap.read()
            if not ok:
                break
            yield FrameSample(index=i, time_s=i / self.fps,
                              view_crops=split_views(frame, self.split))
            i += 1

    def read_composite(self):
        """Return the next raw composite frame (full, unsplit), or None."""
        ok, frame = self._cap.read()
        return frame if ok else None

    def close(self) -> None:
        self._cap.release()


def _enumerate_device_names():
    """Friendly names of connected video devices, index-ordered. Uses pygrabber
    (DirectShow) on Windows; falls back to probing indices 0..5."""
    try:
        from pygrabber.dshow_graph import FilterGraph
        return list(FilterGraph().get_input_devices())
    except Exception:
        names = []
        for i in range(6):
            cap = cv2.VideoCapture(i)
            opened = cap.isOpened()
            cap.release()
            if opened:
                names.append(f"Camera {i}")
            elif names:
                break  # stop at first gap once we've found at least one
        return names


def list_cameras(_enumerator=None):
    """Return [{index, name}] for connected cameras. `_enumerator` is injectable
    for tests (a callable returning a list of friendly names)."""
    names = (_enumerator or _enumerate_device_names)()
    return [{"index": i, "name": n} for i, n in enumerate(names)]


class DualCameraSource(FrameSource):
    """Combine TWO USB cameras into one side-by-side composite (left half =
    down_line, right half = face_on), so the rest of the pipeline (split_views,
    detect_board, triangulation) is unchanged. Each camera free-runs on its own
    clock — fine for a held-still checkerboard; see the spec for the live-motion
    sync caveat. `cap_factory` is injectable for tests."""

    def __init__(self, left_index: int, right_index: int,
                 split: float = C.DEFAULT_SPLIT, cap_factory=None):
        factory = cap_factory or (lambda i: cv2.VideoCapture(i))
        self._left = factory(left_index)
        self._right = factory(right_index)
        if not self._left.isOpened() or not self._right.isOpened():
            raise RuntimeError(
                f"could not open both cameras (left={left_index}, right={right_index})")
        self.split = split
        self._w = int(self._left.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
        self._h = int(self._left.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480
        self.width = self._w * 2          # composite is two equal halves
        self.height = self._h
        self.fps = float(self._left.get(cv2.CAP_PROP_FPS)) or 30.0

    def _grab(self):
        okl, fl = self._left.read()
        okr, fr = self._right.read()
        if not (okl and okr):
            return None
        # Resize both to the left camera's size so the composite splits at 0.5.
        fl = cv2.resize(fl, (self._w, self._h))
        fr = cv2.resize(fr, (self._w, self._h))
        import numpy as _np
        return _np.hstack([fl, fr])       # left = down_line, right = face_on

    def read_composite(self):
        return self._grab()

    def frames(self) -> Iterator[FrameSample]:
        i = 0
        while True:
            comp = self._grab()
            if comp is None:
                break
            yield FrameSample(index=i, time_s=i / self.fps,
                              view_crops=split_views(comp, self.split))
            i += 1

    def close(self) -> None:
        self._left.release()
        self._right.release()
