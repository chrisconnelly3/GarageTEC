"""Pluggable camera calibration for triangulation.

Each Calibration yields two 3x4 projection matrices P = K[R|t] (world->image,
pixels) and a world frame {origin, up, target_line, depth}. AssumedGeometry is
an approximate provider for uncalibrated ~90-degree rigs (dev / smooth_swing.mov);
CheckerboardCalibration (Task 11) loads a real OpenCV stereo calibration.
"""
from typing import Dict, Tuple

import numpy as np

VIEW_FACE_ON = "face_on"
VIEW_DOWN_LINE = "down_line"
SHOULDER_HEIGHT_RATIO = 0.24
IN_TO_M = 0.0254


class Calibration:
    """Interface: projection_matrices() -> (P_face_on, P_down_line);
    world_frame() -> {origin, up, target_line, depth}; confidence tag."""
    confidence = "unknown"

    def projection_matrices(self) -> Tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def world_frame(self) -> Dict[str, object]:
        raise NotImplementedError


def _intrinsics(image_width, image_height, focal_px):
    cx, cy = image_width / 2.0, image_height / 2.0
    return np.array([[focal_px, 0, cx],
                     [0, focal_px, cy],
                     [0, 0, 1]], dtype=float)


def _projection(K, R, t):
    """P = K [R | t], where [R|t] maps world points into the camera frame."""
    Rt = np.hstack([R, t.reshape(3, 1)])
    return K @ Rt


class AssumedGeometryCalibration(Calibration):
    """Orthogonal ~90-degree rig, no calibration target. APPROXIMATE."""
    confidence = "medium"

    def __init__(self, image_width, image_height, height_in,
                 focal_px=None, camera_distance_m=4.0):
        self.image_width = image_width
        self.image_height = image_height
        # default focal ~ image width => ~53 deg horizontal FOV (typical).
        self.focal_px = float(focal_px or image_width)
        self.height_in = height_in
        self.d = camera_distance_m
        # metric scale carried for downstream sanity (subject shoulder width).
        self.shoulder_width_m = SHOULDER_HEIGHT_RATIO * height_in * IN_TO_M

    def projection_matrices(self):
        K = _intrinsics(self.image_width, self.image_height, self.focal_px)
        # Face-on camera on +Z, looking toward origin (-Z). Camera axes:
        # x_cam = world +X (right), y_cam = world -Y (image y grows down),
        # z_cam = world -Z (viewing dir points from camera toward subject).
        R_fo = np.array([[1, 0, 0],
                         [0, -1, 0],
                         [0, 0, -1]], dtype=float)
        t_fo = np.array([0, 0, self.d], dtype=float)   # see note below
        # Down-line camera on +X, looking toward origin (-X) (rotate 90 about Y).
        R_dl = np.array([[0, 0, 1],
                         [0, -1, 0],
                         [-1, 0, 0]], dtype=float)
        t_dl = np.array([0, 0, self.d], dtype=float)
        return _projection(K, R_fo, t_fo), _projection(K, R_dl, t_dl)

    def world_frame(self):
        return {"origin": np.array([0.0, 0.0, 0.0]),
                "up": np.array([0.0, 1.0, 0.0]),
                "target_line": np.array([1.0, 0.0, 0.0]),
                "depth": np.array([0.0, 0.0, 1.0])}


import json as _json


class CheckerboardCalibration(Calibration):
    """Loads a stereo calibration (from the in-app calibration or the CLI).
    HIGH confidence."""
    confidence = "high"

    def __init__(self, calib: dict):
        self._c = calib
        self.K_fo = np.array(calib["K_face_on"], float)
        self.K_dl = np.array(calib["K_down_line"], float)
        self.R_fo = np.array(calib["R_face_on"], float)
        self.t_fo = np.array(calib["t_face_on"], float)
        self.R_dl = np.array(calib["R_down_line"], float)
        self.t_dl = np.array(calib["t_down_line"], float)

    @classmethod
    def from_dict(cls, calib: dict):
        return cls(calib)

    @classmethod
    def from_file(cls, path: str):
        with open(path, "r", encoding="utf-8") as f:
            return cls(_json.load(f))

    def projection_matrices(self):
        return (_projection(self.K_fo, self.R_fo, self.t_fo),
                _projection(self.K_dl, self.R_dl, self.t_dl))

    def world_frame(self):
        return {"origin": np.array([0.0, 0.0, 0.0]),
                "up": np.array(self._c["up"], float),
                "target_line": np.array(self._c["target_line"], float),
                "depth": np.array(self._c["depth"], float)}


def active_calibration(conn, image_width=None, image_height=None, height_in=70.0):
    """Return CheckerboardCalibration for the active stored calibration, or an
    AssumedGeometryCalibration fallback (needs image dims for the fallback)."""
    from store import repo
    row = repo.get_active_calibration(conn)
    if row is not None:
        import json
        # A malformed/empty calib_json (e.g. a stub "{}") must NOT crash the
        # whole pipeline — treat it as "no usable calibration" and fall through
        # to the assumed-geometry fallback.
        try:
            return CheckerboardCalibration.from_dict(json.loads(row.calib_json))
        except (ValueError, KeyError, TypeError):
            pass
    if image_width and image_height:
        return AssumedGeometryCalibration(image_width, image_height, height_in)
    return None
