# vision/threed/checkerboard.py
"""Pure checkerboard calibration engine (no web, no device).

detect_board: find the board in each half of a composite frame.
coverage_cell: bucket the board center into a grid (drives the coverage map).
stereo_calibrate: cv2.stereoCalibrate over accumulated corner pairs -> the
bay_calib.json dict + reprojection error.
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

IN_TO_M = 0.0254
_CRIT = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)


@dataclass
class BoardDetection:
    found_both: bool
    fo_corners: Optional[np.ndarray]   # (N,1,2) float32 in FO-half pixels
    dl_corners: Optional[np.ndarray]
    fo_center: Optional[Tuple[float, float]]
    dl_center: Optional[Tuple[float, float]]


@dataclass
class CalibrationResult:
    calib: dict                # the bay_calib.json dict
    reprojection_error: float
    n_poses: int


def _split(composite, split):
    w = composite.shape[1]
    x = int(round(w * split))
    return composite[:, x:], composite[:, :x]   # (face_on=right, down_line=left)


def _find(gray, cols, rows):
    ok, corners = cv2.findChessboardCorners(
        gray, (cols, rows),
        flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE)
    if not ok:
        return None, None
    corners = cv2.cornerSubPix(gray, corners, (11, 11), (-1, -1), _CRIT)
    center = (float(corners[:, 0, 0].mean()), float(corners[:, 0, 1].mean()))
    return corners, center


def detect_board(composite, cols, rows, split=0.5, mono=False) -> BoardDetection:
    """Find the checkerboard in each half of the composite (the two camera
    views). `mono=True` (single-camera test mode) runs detection on the WHOLE
    frame and reuses those corners for both views — for a laptop webcam that
    shows ONE board which the 50/50 split would otherwise bisect into neither
    half. Mono stereo is degenerate (zero baseline); it validates the live
    capture/detect/preview/coverage plumbing only, not real geometry."""
    if mono:
        gray = cv2.cvtColor(composite, cv2.COLOR_BGR2GRAY)
        c, ctr = _find(gray, cols, rows)
        return BoardDetection(found_both=(c is not None),
                              fo_corners=c, dl_corners=c,
                              fo_center=ctr, dl_center=ctr)
    fo, dl = _split(composite, split)
    g_fo = cv2.cvtColor(fo, cv2.COLOR_BGR2GRAY)
    g_dl = cv2.cvtColor(dl, cv2.COLOR_BGR2GRAY)
    fo_c, fo_ctr = _find(g_fo, cols, rows)
    dl_c, dl_ctr = _find(g_dl, cols, rows)
    return BoardDetection(found_both=(fo_c is not None and dl_c is not None),
                          fo_corners=fo_c, dl_corners=dl_c,
                          fo_center=fo_ctr, dl_center=dl_ctr)


def coverage_cell(center, image_size, grid=(4, 3)):
    """Grid cell (col,row) the board center falls in. image_size=(w,h)."""
    w, h = image_size
    gx, gy = grid
    cx = min(gx - 1, max(0, int(center[0] / max(w, 1) * gx)))
    cy = min(gy - 1, max(0, int(center[1] / max(h, 1) * gy)))
    return (cx, cy)


def _object_points(cols, rows, square_m):
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_m
    return objp


def stereo_calibrate(object_points, fo_pts, dl_pts, image_size, square_m,
                     K_fo=None, K_dl=None) -> CalibrationResult:
    """Calibrate from accumulated corner pairs. If K_* are None, intrinsics are
    estimated per view first, then fixed for the stereo solve. Face-on is the
    world reference (R=I, t=0); down_line carries the relative [R|T]."""
    w, h = image_size
    if K_fo is None:
        _, K_fo, d_fo, _, _ = cv2.calibrateCamera(object_points, fo_pts, (w, h), None, None)
    else:
        d_fo = np.zeros(5)
    if K_dl is None:
        _, K_dl, d_dl, _, _ = cv2.calibrateCamera(object_points, dl_pts, (w, h), None, None)
    else:
        d_dl = np.zeros(5)
    err, K_fo, d_fo, K_dl, d_dl, R, T, _, _ = cv2.stereoCalibrate(
        object_points, fo_pts, dl_pts, K_fo, d_fo, K_dl, d_dl, (w, h),
        flags=cv2.CALIB_FIX_INTRINSIC, criteria=_CRIT)
    calib = {
        "image_width": int(w), "image_height": int(h),
        "K_face_on": K_fo.tolist(), "K_down_line": K_dl.tolist(),
        "R_face_on": np.eye(3).tolist(), "t_face_on": [0.0, 0.0, 0.0],
        "R_down_line": R.tolist(), "t_down_line": T.ravel().tolist(),
        # world axes in the face-on camera frame (board defines target line/ground);
        # flip a sign here if turn reads reversed (see the calibration guide).
        "up": [0, -1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }
    return CalibrationResult(calib=calib, reprojection_error=float(err),
                             n_poses=len(object_points))
