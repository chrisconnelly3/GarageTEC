import numpy as np
from vision.threed.reconstruct import reconstruct
from vision.threed.calibration import AssumedGeometryCalibration
from vision.threed import pipeline3d
from vision.types import PoseTimeline
from store.models import Landmark


def _proj(P, X):
    uvw = P @ np.array([X[0], X[1], X[2], 1.0]); return uvw[0]/uvw[2], uvw[1]/uvw[2]


def test_pipeline3d_reconstructs_window_to_index_map():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    pts = {"left_shoulder": np.array([0.18, 1.4, 0.0]),
           "right_shoulder": np.array([-0.18, 1.4, 0.0])}
    for k in range(3):
        for tl, P in ((fo, P1), (dl, P2)):
            tl.times_s.append(k / 30.0)
            tl.frames.append([Landmark(n, *_proj(P, X), 0.0, 0.99)
                              for n, X in pts.items()])
    frames_by_index = pipeline3d.reconstruct_window(fo, dl, cal,
                                                    start_index=0, end_index=2)
    assert set(frames_by_index.keys()) == {0, 1, 2}
    by = {l.name: l for l in frames_by_index[0]}
    assert abs(by["left_shoulder"].x - 0.18) < 1e-4
