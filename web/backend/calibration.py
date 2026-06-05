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
from vision.frames import LiveCameraSource, DualCameraSource
from vision.threed.checkerboard import (
    detect_board, coverage_cell, estimate_tilt_deg, stereo_calibrate,
    _object_points)

# Varied-angle pose collection: accept a pose only if it adds a new
# (position cell, tilt bucket) combination, so reaching the target requires
# genuine position AND angle variety. Targets per the two-camera design.
MIN_RUN_POSES = 15        # minimum to allow a real (two-camera) calibration
TARGET_POSES = 24         # auto-run once this many varied poses collected
MAX_POSES = 30            # stop accepting beyond this
TILT_BUCKET_DEG = 12      # board-tilt bucket width (deg) for angle variety


class CalibrationEventBus:
    def __init__(self):
        self._lock = threading.Lock(); self._events = []
    def publish(self, event, data):
        with self._lock: self._events.append({"event": event, "data": data})
    def drain(self):
        with self._lock:
            out = self._events; self._events = []; return out


class CalibrationSupervisor:
    def __init__(self, *, conn, bus):
        self.conn = conn
        self.bus = bus
        self._lock = threading.Lock()
        self._run = False
        self._thread = None
        self._source = None
        self._reset_state()

    def _reset_state(self):
        self.cols = self.rows = 0
        self.square_mm = 25.0
        self.device_left = 0
        self.device_right = None
        self.split = 0.5
        self.mono = False
        self.image_size = None
        self._obj, self._fo, self._dl = [], [], []
        self._covered = set()        # position cells seen (drives the grid UI)
        self._tilt_buckets = set()   # tilt buckets seen (angle variety)
        self._seen = set()           # (cell, tilt_bucket) accepted combos
        self._overlay_jpeg = None
        self._capturing = False

    # ---- testable core (no thread/device) --------------------------------
    def process_frame(self, composite) -> bool:
        det = detect_board(composite, self.cols, self.rows, self.split,
                           mono=self.mono)
        h, w = composite.shape[:2]
        # mono = single webcam: the whole frame is the "view"; otherwise a half.
        half = (w, h) if self.mono else (int(w * (1 - self.split)), h)
        self.image_size = half
        accepted = False
        if det.found_both and len(self._obj) < MAX_POSES:
            cell = coverage_cell(det.fo_center, half)
            tilt = estimate_tilt_deg(det.fo_corners, self.cols, self.rows, half)
            bucket = int(tilt // TILT_BUCKET_DEG)
            key = (cell, bucket)
            # Accept only NEW (position, angle) combos -> forces varied poses.
            if key not in self._seen:
                self._seen.add(key)
                self._covered.add(cell)
                self._tilt_buckets.add(bucket)
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
            if self.mono:
                cv2.drawChessboardCorners(img, (self.cols, self.rows),
                                          det.fo_corners, True)
            else:
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
                "tilt_buckets": len(self._tilt_buckets),
                "min_poses": MIN_RUN_POSES, "target_poses": TARGET_POSES,
                "max_poses": MAX_POSES,
                "device_left": self.device_left, "device_right": self.device_right,
                "mono": self.mono, "cols": self.cols, "rows": self.rows}

    # ---- start/stop/run ---------------------------------------------------
    def configure(self, *, device_left, device_right=None, cols, rows, square_mm,
                  mono=False):
        """Set params + clear accumulation WITHOUT opening a device or spawning
        the capture thread. The thread-free path used by tests and by start().
        Two cameras: device_left = down-line, device_right = face-on. `mono` =
        single-camera (webcam) test mode (uses device_left only)."""
        self._reset_state()
        self.device_left, self.device_right = device_left, device_right
        self.cols, self.rows = cols, rows
        self.square_mm = square_mm
        self.mono = mono

    def _make_source(self):
        """Build the capture source from the current config: a single webcam in
        mono test mode, else two USB cameras combined into a composite."""
        if self.mono or self.device_right is None:
            return LiveCameraSource(device_index=self.device_left, split=self.split)
        return DualCameraSource(self.device_left, self.device_right,
                                split=self.split)

    def start(self, *, device_left, device_right=None, cols, rows, square_mm,
              mono=False, source_factory=None):
        with self._lock:
            if self._run:
                return
            self.configure(device_left=device_left, device_right=device_right,
                           cols=cols, rows=rows, square_mm=square_mm, mono=mono)
            self._source = (source_factory() if source_factory
                            else self._make_source())
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
        if self.mono:
            # One camera can't yield a real stereo calibration (zero baseline).
            # The smoke test only validates capture/detection plumbing.
            return {"ok": False, "mono": True, "n_poses": len(self._obj),
                    "error": "single-camera test mode: live capture + board "
                             "detection validated; real calibration needs the "
                             "two-camera bay."}
        if len(self._obj) < MIN_RUN_POSES:
            return {"ok": False,
                    "error": f"only {len(self._obj)} poses; need >= {MIN_RUN_POSES}",
                    "n_poses": len(self._obj)}
        size = self.image_size or (640, 480)
        res = stereo_calibrate(self._obj, self._fo, self._dl, size,
                               self.square_mm / 1000.0)
        import json
        repo.save_calibration(
            self.conn, device_index=self.device_left, cols=self.cols,
            rows=self.rows, square_mm=self.square_mm, n_poses=res.n_poses,
            reprojection_error=res.reprojection_error,
            calib_json=json.dumps(res.calib))
        self.bus.publish("calibration_done",
                         {"n_poses": res.n_poses,
                          "reprojection_error": res.reprojection_error})
        return {"ok": True, "n_poses": res.n_poses,
                "reprojection_error": res.reprojection_error}
