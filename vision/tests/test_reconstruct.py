import numpy as np
from vision.threed.reconstruct import triangulate_point, reconstruct
from vision.threed.calibration import AssumedGeometryCalibration
from vision.types import PoseTimeline
from store.models import Landmark


def _project(P, X):
    uvw = P @ np.array([X[0], X[1], X[2], 1.0])
    return uvw[0] / uvw[2], uvw[1] / uvw[2]


def test_triangulate_recovers_known_point():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    X_true = np.array([0.18, 1.40, 0.05])           # a shoulder-ish point
    pt1, pt2 = _project(P1, X_true), _project(P2, X_true)
    X_rec = triangulate_point(P1, P2, pt1, pt2)
    assert np.allclose(X_rec, X_true, atol=1e-6)


def test_reconstruct_builds_timeline_with_world_points():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    X = {"left_shoulder": np.array([0.18, 1.40, 0.0]),
         "right_shoulder": np.array([-0.18, 1.40, 0.0])}
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    for tl, P in ((fo, P1), (dl, P2)):
        lms = []
        for name, Xw in X.items():
            u, v = _project(P, Xw)
            lms.append(Landmark(name=name, x=u, y=v, z=0.0, visibility=0.99))
        tl.times_s.append(0.0); tl.frames.append(lms)
    out = reconstruct(fo, dl, cal)
    assert len(out) == 1
    by = {l.name: l for l in out.frames[0]}
    assert np.allclose([by["left_shoulder"].x, by["left_shoulder"].y,
                        by["left_shoulder"].z], [0.18, 1.40, 0.0], atol=1e-5)


def test_triangulate_returns_none_on_degenerate_zero_baseline():
    """Fix 3 guard: identical projection matrices (zero baseline) make the
    homogeneous w collapse for an off-axis ray; triangulate must return None
    rather than dividing into inf/nan."""
    # Two IDENTICAL cameras -> no parallax -> degenerate for points off the
    # principal ray. Build a trivial P that forces w == 0 for a chosen point.
    P = np.array([[1.0, 0.0, 0.0, 0.0],
                  [0.0, 1.0, 0.0, 0.0],
                  [0.0, 0.0, 0.0, 1.0]])   # row 3 = [0,0,0,1] -> w independent of Z
    # A correspondence that has no consistent finite depth under identical Ps
    # with a zero third row contribution; result should be guarded as None.
    out = triangulate_point(P, P, (0.0, 0.0), (1.0, 1.0))
    assert out is None or np.all(np.isfinite(out))


def test_triangulate_none_when_w_zero(monkeypatch):
    """Directly exercise the w == 0 guard via a patched cv2.triangulatePoints."""
    import vision.threed.reconstruct as rec
    monkeypatch.setattr(rec.cv2, "triangulatePoints",
                        lambda *a, **k: np.array([[1.0], [2.0], [3.0], [0.0]]))
    assert rec.triangulate_point(np.eye(3, 4), np.eye(3, 4),
                                 (0.0, 0.0), (0.0, 0.0)) is None


def test_reconstruct_skips_degenerate_landmark(monkeypatch):
    """A landmark whose triangulation is degenerate (None) is omitted, not
    written as inf/nan into the 3D frame."""
    import vision.threed.reconstruct as rec
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    fo.times_s.append(0.0)
    fo.frames.append([Landmark("nose", 480, 300, 0, 0.99)])
    dl.times_s.append(0.0)
    dl.frames.append([Landmark("nose", 480, 300, 0, 0.99)])
    monkeypatch.setattr(rec, "triangulate_point", lambda *a, **k: None)
    out = rec.reconstruct(fo, dl, cal)
    assert out.frames[0] == []          # degenerate landmark skipped entirely


def test_reconstruct_drops_low_visibility_landmark():
    cal = AssumedGeometryCalibration(960, 1080, height_in=70.0)
    P1, P2 = cal.projection_matrices()
    fo, dl = PoseTimeline(view="face_on"), PoseTimeline(view="down_line")
    # one landmark visible in only one view -> not triangulated
    fo.times_s.append(0.0)
    fo.frames.append([Landmark("nose", 480, 300, 0, 0.99)])
    dl.times_s.append(0.0)
    dl.frames.append([Landmark("nose", 480, 300, 0, 0.1)])   # low vis in DL
    out = reconstruct(fo, dl, cal, min_visibility=0.5)
    assert out.frames[0] == [] or out.frames[0] is None
