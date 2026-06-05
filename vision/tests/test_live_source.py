# vision/tests/test_live_source.py
import numpy as np
from vision.frames import LiveCameraSource
from vision import constants as C


class _FakeCap:
    """Stand-in for cv2.VideoCapture: yields `n` synthetic BGR frames."""
    def __init__(self, n=3, w=640, h=480):
        self._n, self._i, self._w, self._h = n, 0, w, h
    def isOpened(self): return True
    def get(self, prop):
        import cv2
        return {cv2.CAP_PROP_FRAME_WIDTH: self._w,
                cv2.CAP_PROP_FRAME_HEIGHT: self._h,
                cv2.CAP_PROP_FPS: 30.0}.get(prop, 0)
    def read(self):
        if self._i >= self._n:
            return False, None
        self._i += 1
        return True, np.full((self._h, self._w, 3), self._i, dtype=np.uint8)
    def release(self): pass


def test_live_source_yields_split_frames():
    src = LiveCameraSource(device_index=0, max_frames=3,
                           cap_factory=lambda i: _FakeCap(n=3))
    assert src.width == 640 and src.height == 480 and src.fps == 30.0
    samples = list(src.frames())
    assert len(samples) == 3
    s = samples[0]
    assert C.VIEW_DOWN_LINE in s.view_crops and C.VIEW_FACE_ON in s.view_crops
    # each half is ~ half width
    assert s.view_crops[C.VIEW_FACE_ON].shape[1] == 320
    src.close()


def test_read_composite_returns_full_frame():
    src = LiveCameraSource(device_index=0, cap_factory=lambda i: _FakeCap(n=1))
    frame = src.read_composite()
    assert frame is not None and frame.shape == (480, 640, 3)
    assert src.read_composite() is None     # exhausted
    src.close()


# --- camera enumeration + dual source -----------------------------------------
from vision.frames import list_cameras, DualCameraSource
from vision import constants as C2


def test_list_cameras_structure_with_injected_enumerator():
    cams = list_cameras(_enumerator=lambda: ["Logitech BRIO", "Integrated Webcam"])
    assert cams == [{"index": 0, "name": "Logitech BRIO"},
                    {"index": 1, "name": "Integrated Webcam"}]


def test_list_cameras_empty():
    assert list_cameras(_enumerator=lambda: []) == []


class _FakeCap2:
    def __init__(self, val, n=3, w=320, h=240):
        self._val, self._n, self._i, self._w, self._h = val, n, 0, w, h
    def isOpened(self): return True
    def get(self, prop):
        import cv2
        return {cv2.CAP_PROP_FRAME_WIDTH: self._w, cv2.CAP_PROP_FRAME_HEIGHT: self._h,
                cv2.CAP_PROP_FPS: 30.0}.get(prop, 0)
    def read(self):
        if self._i >= self._n: return False, None
        self._i += 1
        return True, np.full((self._h, self._w, 3), self._val, dtype=np.uint8)
    def release(self): pass


def test_dual_camera_source_combines_two_streams():
    caps = {0: _FakeCap2(10), 1: _FakeCap2(20)}
    src = DualCameraSource(left_index=0, right_index=1, cap_factory=lambda i: caps[i])
    comp = src.read_composite()
    assert comp is not None
    # composite = left | right, each resized to the left's (w,h) -> 2*320 wide
    assert comp.shape == (240, 640, 3)
    # left half came from cap 0 (value 10), right half from cap 1 (value 20)
    assert comp[0, 0, 0] == 10 and comp[0, 639, 0] == 20
    samples = list(src.frames())
    assert len(samples) == 2          # 3 frames available, but read_composite took 1
    assert C2.VIEW_DOWN_LINE in samples[0].view_crops
    src.close()
