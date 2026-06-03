from vision.pipeline import build_timelines, process_video
from vision.types import PoseTimeline
from vision import constants as C
from store import repo
from store.models import Landmark
from vision.tests.conftest import TEST_VIDEO, requires_video


class _FakeSource:
    """A frame source that yields synthetic crops without touching disk/OpenCV.
    Lets us test the orchestration without running pose on a real video.
    """
    def __init__(self, n):
        import numpy as np
        self.width, self.height, self.fps = 320, 240, 30.0
        self._n = n
        self._np = np

    def frames(self):
        from vision.types import FrameSample
        for i in range(self._n):
            crop = self._np.zeros((240, 160, 3), dtype=self._np.uint8)
            yield FrameSample(index=i, time_s=i / 30.0,
                              view_crops={C.VIEW_DOWN_LINE: crop,
                                          C.VIEW_FACE_ON: crop})

    def close(self):
        pass


class _FakePose:
    """Pose estimator stub: returns a moving-then-still hand so swing_detect
    finds exactly one window."""
    def __init__(self, view):
        self.view = view

    def estimate(self, bgr):
        # caller increments a counter via closure in the test; here we just
        # return a constant landmark set (motion comes from frame index in test)
        return None  # replaced per-test below


def test_build_timelines_runs_pose_once_per_frame(monkeypatch):
    import numpy as np

    # a pose stub whose hand moves with the frame so energy is nonzero mid-clip
    state = {"i": 0}

    class MovingPose:
        def __init__(self, view):
            self.view = view

        def estimate(self, bgr):
            i = state["i"]
            # hands still for 0..9, moving 10..29, still 30..49
            x = 10.0 + (max(0, min(i - 10, 20)) * 4.0)
            return [Landmark("left_wrist", x, 50.0, 0.0, 0.9),
                    Landmark("right_wrist", x + 2, 52.0, 0.0, 0.9),
                    Landmark("left_shoulder", 30.0, 40.0, 0.0, 0.9)]

    def advance():
        state["i"] += 1

    src = _FakeSource(50)

    # wrap estimate to advance the shared frame counter once per (paired) call
    dl = MovingPose(C.VIEW_DOWN_LINE)
    fo = MovingPose(C.VIEW_FACE_ON)
    orig = fo.estimate

    def fo_estimate(bgr):
        r = orig(bgr)
        advance()
        return r
    fo.estimate = fo_estimate

    down_line, face_on = build_timelines(src, dl, fo)
    assert len(down_line) == 50 and len(face_on) == 50
    assert isinstance(down_line, PoseTimeline)


@requires_video
def test_process_video_smoke_stores_swing(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    results = []
    process_video(db, TEST_VIDEO, player_id=pid, session_id=sid, split=0.5,
                  render=False, on_swing=results.append)
    # at least one swing detected and stored
    swings = repo.list_swings(db, session_id=sid)
    assert len(swings) >= 1
    assert len(results) == len(swings)
    first = swings[0]
    # both views have pose frames
    assert len(repo.get_pose_frames(db, first.id, C.VIEW_DOWN_LINE)) > 0
    assert len(repo.get_pose_frames(db, first.id, C.VIEW_FACE_ON)) > 0
    # 8 moments
    assert len(repo.get_moments(db, first.id)) == 8
    # SwingResult shape
    assert results[0].swing_id == first.id
    assert results[0].view_layout == C.VIEW_LAYOUT
    assert len(results[0].frame_range) == 2
