from store import db as dbmod, repo
from vision.threed.calibration import active_calibration, CheckerboardCalibration
from vision import constants as C
from store.models import Landmark


def test_active_calibration_prefers_stored_then_falls_back():
    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    # none stored -> AssumedGeometry fallback when dims given
    cal = active_calibration(conn, image_width=1214, image_height=1284)
    assert cal is not None and cal.__class__.__name__ == "AssumedGeometryCalibration"
    # store one -> CheckerboardCalibration returned
    repo.save_calibration(conn, device_index=0, cols=9, rows=6, square_mm=25.0,
                          n_poses=20, reprojection_error=0.4,
                          calib_json='{"image_width":640,"image_height":480,'
                          '"K_face_on":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"K_down_line":[[800,0,320],[0,800,240],[0,0,1]],'
                          '"R_face_on":[[1,0,0],[0,1,0],[0,0,1]],"t_face_on":[0,0,0],'
                          '"R_down_line":[[1,0,0],[0,1,0],[0,0,1]],"t_down_line":[0,0,0.5],'
                          '"up":[0,-1,0],"target_line":[1,0,0],"depth":[0,0,1]}')
    cal2 = active_calibration(conn, image_width=1214, image_height=1284)
    assert isinstance(cal2, CheckerboardCalibration) and cal2.confidence == "high"


class _CompositeFakeSource:
    """Frame source whose composite is W x H; split_views would crop the
    face_on (right) view to (W - round(W*split)) wide. The pose stub returns a
    moving-then-still hand so exactly one swing window is detected."""

    def __init__(self, n, width, height, split):
        import numpy as np
        self.width, self.height, self.fps = width, height, 30.0
        self._n, self._np, self._split = n, np, split

    def frames(self):
        from vision.types import FrameSample
        for i in range(self._n):
            crop = self._np.zeros((self.height, self.width // 2, 3),
                                  dtype=self._np.uint8)
            yield FrameSample(index=i, time_s=i / 30.0,
                              view_crops={C.VIEW_DOWN_LINE: crop,
                                          C.VIEW_FACE_ON: crop})

    def close(self):
        pass


def test_assumed_geometry_built_with_half_view_width(monkeypatch):
    """Fix 1 regression: when no stored calibration exists, process_video must
    build the AssumedGeometry fallback with the PER-VIEW (half) width that
    matches the half-crop landmark coords, NOT the full composite width."""
    import numpy as np
    from vision import pipeline as pipe

    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    pid = repo.get_or_create_player(conn, "Chris", 72.0, "R").id
    sid = repo.create_session(conn, pid).id

    COMPOSITE_W, COMPOSITE_H, SPLIT = 1280, 720, 0.5

    # Fake source instead of opening a real video file.
    monkeypatch.setattr(pipe, "VideoFileSource",
                        lambda path, split=0.5: _CompositeFakeSource(
                            60, COMPOSITE_W, COMPOSITE_H, split))

    # Pose stub: moving-then-still hand -> exactly one detected swing window.
    state = {"i": 0}

    class _Pose:
        def __init__(self, view):
            self.view = view

        def estimate(self, bgr):
            i = state["i"]
            # Hand HEIGHT trajectory (mean wrist image-y; smaller y = higher):
            # address ~200 for 0..14, rises to apex ~40 around frame 30, falls
            # back to address by ~45 and stays -> exactly one excursion/return.
            up = max(0, min(i - 15, 15))      # 0..15 over frames 15..30
            down = max(0, min(i - 30, 15))    # 0..15 over frames 30..45
            y = 200.0 - up * 10.0 + down * 10.0   # 200 -> 50 -> 200
            return [Landmark("left_wrist", 100.0, y, 0.0, 0.9),
                    Landmark("right_wrist", 102.0, y + 2, 0.0, 0.9),
                    Landmark("left_shoulder", 30.0, 40.0, 0.0, 0.9)]

        def close(self):
            pass

    fo_seen = {}
    orig_estimate = _Pose.estimate

    def _fo_estimate(self, bgr):
        r = orig_estimate(self, bgr)
        if self.view == C.VIEW_FACE_ON:
            state["i"] += 1
        return r

    monkeypatch.setattr(_Pose, "estimate", _fo_estimate)
    monkeypatch.setattr(pipe, "make_pose_estimator",
                        lambda view, backend=None: _Pose(view=view))

    # Capture the image dims active_calibration is built with.
    captured = {}

    def _fake_active_calibration(conn, image_width=None, image_height=None,
                                 height_in=70.0):
        captured["width"] = image_width
        captured["height"] = image_height
        return None  # skip 3D reconstruction in this test

    monkeypatch.setattr("vision.threed.calibration.active_calibration",
                        _fake_active_calibration)

    pipe.process_video(conn, "dummy.mp4", player_id=pid, session_id=sid,
                       split=SPLIT, render=False)

    expected_half = COMPOSITE_W - int(round(COMPOSITE_W * SPLIT))
    assert captured["width"] == expected_half, (
        f"expected half width {expected_half}, got {captured['width']} "
        f"(composite was {COMPOSITE_W})")
    assert captured["width"] != COMPOSITE_W
    assert captured["height"] == COMPOSITE_H
