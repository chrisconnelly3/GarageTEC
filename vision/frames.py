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
