# vision/tests/test_checkerboard.py
import cv2
import numpy as np
from vision.threed import checkerboard as cb


def _render_checkerboard(cols, rows, square=40, border=40):
    """Render a (cols+1)x(rows+1)-square board -> cols x rows inner corners."""
    w = (cols + 1) * square + 2 * border
    h = (rows + 1) * square + 2 * border
    img = np.full((h, w), 255, np.uint8)
    for r in range(rows + 1):
        for c in range(cols + 1):
            if (r + c) % 2 == 0:
                y0, x0 = border + r * square, border + c * square
                img[y0:y0 + square, x0:x0 + square] = 0
    return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)


def test_detect_board_finds_corners_in_both_halves():
    half = _render_checkerboard(9, 6)
    composite = np.hstack([half, half])        # left=DL, right=FO, same board
    det = cb.detect_board(composite, cols=9, rows=6, split=0.5)
    assert det.found_both
    assert det.fo_corners.shape[0] == 9 * 6 and det.dl_corners.shape[0] == 9 * 6
    assert det.fo_center is not None and det.dl_center is not None


def test_detect_board_mono_uses_whole_frame():
    # A single webcam shows ONE board: with the 50/50 split it is bisected and
    # found in NEITHER half (the bug); mono=True detects it on the whole frame.
    board = _render_checkerboard(9, 6)
    assert cb.detect_board(board, cols=9, rows=6, split=0.5).found_both is False
    det = cb.detect_board(board, cols=9, rows=6, mono=True)
    assert det.found_both
    assert det.fo_corners.shape[0] == 9 * 6
    # mono uses the same corners for both views (degenerate stereo, plumbing only)
    assert det.fo_corners is det.dl_corners
    assert det.fo_center == det.dl_center


def test_coverage_cell_buckets_position():
    assert cb.coverage_cell((10, 10), (400, 300), grid=(4, 3)) == (0, 0)
    assert cb.coverage_cell((399, 299), (400, 300), grid=(4, 3)) == (3, 2)


def test_stereo_calibrate_recovers_known_geometry():
    cols, rows, square_m = 9, 6, 0.025
    # object points (board plane), grid of cols*rows inner corners in meters
    objp = np.zeros((cols * rows, 3), np.float32)
    objp[:, :2] = np.mgrid[0:cols, 0:rows].T.reshape(-1, 2) * square_m
    K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], float)
    # two camera views of the board at a few placements
    fo_pts, dl_pts, obj_list = [], [], []
    rng_rots = [(-0.2, 0.1, 0.0), (0.1, -0.15, 0.05), (0.0, 0.2, -0.1),
                (0.15, 0.1, 0.1), (-0.1, -0.1, 0.0), (0.05, 0.05, -0.05)]
    for rot in rng_rots:
        rvec = np.array(rot, float)
        tvec_fo = np.array([-0.1, -0.08, 0.6], float)
        tvec_dl = np.array([-0.1, -0.08, 0.6], float)
        # DL camera rotated 30 deg about Y relative to FO -> different projection
        R_rel, _ = cv2.Rodrigues(np.array([0, 0.5236, 0], float))
        fo, _ = cv2.projectPoints(objp, rvec, tvec_fo, K, None)
        Rb, _ = cv2.Rodrigues(rvec)
        objp_cam = (R_rel @ (Rb @ objp.T + tvec_fo.reshape(3, 1)))
        dl, _ = cv2.projectPoints(objp_cam.T.astype(np.float32),
                                  np.zeros(3), np.zeros(3), K, None)
        fo_pts.append(fo.reshape(-1, 1, 2).astype(np.float32))
        dl_pts.append(dl.reshape(-1, 1, 2).astype(np.float32))
        obj_list.append(objp.copy())
    res = cb.stereo_calibrate(obj_list, fo_pts, dl_pts, image_size=(640, 480),
                              square_m=square_m, K_fo=K, K_dl=K)
    assert res.reprojection_error < 1.0          # px
    R_rel_out = np.array(res.calib["R_down_line"])
    rvec_out, _ = cv2.Rodrigues(R_rel_out)
    assert abs(abs(rvec_out[1, 0]) - 0.5236) < 0.05   # ~30 deg about Y recovered
    assert "image_width" in res.calib and res.calib["image_width"] == 640
