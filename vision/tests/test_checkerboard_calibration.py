import numpy as np
from vision.threed.calibration import CheckerboardCalibration


def _calib():
    return {
        "image_width": 640, "image_height": 480,
        "K_face_on": [[800, 0, 320], [0, 800, 240], [0, 0, 1]],
        "K_down_line": [[800, 0, 320], [0, 800, 240], [0, 0, 1]],
        "R_face_on": [[1, 0, 0], [0, 1, 0], [0, 0, 1]], "t_face_on": [0, 0, 0],
        "R_down_line": [[0, 0, 1], [0, 1, 0], [-1, 0, 0]], "t_down_line": [0, 0, 0.5],
        "up": [0, -1, 0], "target_line": [1, 0, 0], "depth": [0, 0, 1],
    }


def test_provider_from_dict_projects():
    cal = CheckerboardCalibration.from_dict(_calib())
    P_fo, P_dl = cal.projection_matrices()
    assert P_fo.shape == (3, 4) and P_dl.shape == (3, 4)
    assert cal.confidence == "high"
    assert np.allclose(cal.world_frame()["target_line"], [1, 0, 0])
