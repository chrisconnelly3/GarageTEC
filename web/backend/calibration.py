"""In-app camera calibration engine (mirrors CaptureSupervisor).

CalibrationEventBus: thread-safe event buffer (publish from the capture thread;
SSE coroutine drains). CalibrationSupervisor: owns a LiveCameraSource, detects
the board per frame, accumulates new-coverage good poses, keeps an overlay JPEG
for MJPEG, and run() stereo-calibrates + persists. process_frame() is the
thread-free testable core.
"""
import threading
from typing import Callable, Optional

import cv2
import numpy as np

from store import repo
from vision.frames import LiveCameraSource
from vision.threed.checkerboard import (
    detect_board, coverage_cell, stereo_calibrate, _object_points)


class CalibrationEventBus:
    def __init__(self):
        self._lock = threading.Lock(); self._events = []
    def publish(self, event, data):
        with self._lock: self._events.append({"event": event, "data": data})
    def drain(self):
        with self._lock:
            out = self._events; self._events = []; return out


def _default_source_factory(device_index, split):
    return LiveCameraSource(device_index=device_index, split=split)


class CalibrationSupervisor:
    def __init__(self, *, conn, bus, source_factory: Callable = _default_source_factory):
        self.conn = conn
        self.bus = bus
        self._source_factory = source_factory
        self._lock = threading.Lock()
        self._run = False
        self._thread = None
        self._source = None
        self._reset_state()

    def _reset_state(self):
        self.cols = self.rows = 0
        self.square_mm = 25.0
        self.device_index = 0
        self.split = 0.5
        self.image_size = None
        self._obj, self._fo, self._dl = [], [], []
        self._covered = set()
        self._overlay_jpeg = None
        self._capturing = False

    # ---- testable core (no thread/device) --------------------------------
    def process_frame(self, composite) -> bool:
        det = detect_board(composite, self.cols, self.rows, self.split)
        h, w = composite.shape[:2]
        half = (int(w * (1 - self.split)), h)
        self.image_size = half
        accepted = False
        if det.found_both:
            cell = coverage_cell(det.fo_center, half)
            if cell not in self._covered:
                self._covered.add(cell)
                self._obj.append(_object_points(self.cols, self.rows, self.square_mm / 1000.0))
                self._fo.append(det.fo_corners)
                self._dl.append(det.dl_corners)
                accepted = True
        self._overlay_jpeg = self._render_overlay(composite, det)
        self.bus.publish("calibration_status", self.status())
        return accepted

    def _render_overlay(self, composite, det):
        img = composite.copy()
        if det.found_both:
            x0 = int(img.shape[1] * (1 - self.split))
            cv2.drawChessboardCorners(img[:, x0:], (self.cols, self.rows),
                                      det.fo_corners, True)
        ok, buf = cv2.imencode(".jpg", img)
        return buf.tobytes() if ok else None

    def latest_overlay_jpeg(self):
        return self._overlay_jpeg

    def status(self):
        return {"capturing": self._capturing, "good_poses": len(self._obj),
                "coverage": sorted(list(self._covered)),
                "device_index": self.device_index,
                "cols": self.cols, "rows": self.rows}

    # ---- start/stop/run ---------------------------------------------------
    def configure(self, *, device_index, cols, rows, square_mm):
        """Set params + clear accumulation WITHOUT opening a device or spawning
        the capture thread. The thread-free path used by tests and by start()."""
        self._reset_state()
        self.device_index, self.cols, self.rows = device_index, cols, rows
        self.square_mm = square_mm

    def start(self, *, device_index, cols, rows, square_mm, source_factory=None):
        with self._lock:
            if self._run:
                return
            self.configure(device_index=device_index, cols=cols, rows=rows,
                           square_mm=square_mm)
            self._source = (source_factory or self._source_factory)(device_index, self.split)
            self._capturing = True
            self._run = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        import time
        while self._run:
            frame = self._source.read_composite() if self._source else None
            if frame is None:
                time.sleep(0.03); continue
            try:
                self.process_frame(frame)
            except Exception:
                pass

    def stop(self):
        with self._lock:
            self._run = False
            self._capturing = False
        if self._source is not None:
            try: self._source.close()
            except Exception: pass
            self._source = None

    def run(self):
        if len(self._obj) < 8:
            return {"ok": False, "error": f"only {len(self._obj)} poses; need >= 8",
                    "n_poses": len(self._obj)}
        size = self.image_size or (640, 480)
        res = stereo_calibrate(self._obj, self._fo, self._dl, size,
                               self.square_mm / 1000.0)
        import json
        repo.save_calibration(
            self.conn, device_index=self.device_index, cols=self.cols,
            rows=self.rows, square_mm=self.square_mm, n_poses=res.n_poses,
            reprojection_error=res.reprojection_error,
            calib_json=json.dumps(res.calib))
        self.bus.publish("calibration_done",
                         {"n_poses": res.n_poses,
                          "reprojection_error": res.reprojection_error})
        return {"ok": True, "n_poses": res.n_poses,
                "reprojection_error": res.reprojection_error}
