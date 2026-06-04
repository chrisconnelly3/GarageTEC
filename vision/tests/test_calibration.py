import numpy as np
from vision.threed.calibration import AssumedGeometryCalibration


def test_projection_matrices_shape_and_world_frame():
    cal = AssumedGeometryCalibration(image_width=960, image_height=1080,
                                     height_in=70.0)
    P_fo, P_dl = cal.projection_matrices()
    assert P_fo.shape == (3, 4) and P_dl.shape == (3, 4)
    wf = cal.world_frame()
    assert np.allclose(wf["up"], [0, 1, 0])
    assert np.allclose(wf["target_line"], [1, 0, 0])


def test_assumed_geometry_projects_origin_near_image_center():
    cal = AssumedGeometryCalibration(image_width=960, image_height=1080,
                                     height_in=70.0)
    P_fo, _ = cal.projection_matrices()
    X = np.array([0.0, 0.0, 0.0, 1.0])          # world origin (subject center)
    uvw = P_fo @ X
    u, v = uvw[0] / uvw[2], uvw[1] / uvw[2]
    assert abs(u - 480) < 1.0 and abs(v - 540) < 1.0   # ~ image center
