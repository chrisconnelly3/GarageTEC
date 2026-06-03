import numpy as np
from vision.pose import PoseEstimator, LANDMARK_NAMES
from vision.frames import VideoFileSource
from vision import constants as C
from vision.tests.conftest import TEST_VIDEO, requires_video


def test_landmark_names_has_33():
    assert len(LANDMARK_NAMES) == 33
    assert "left_wrist" in LANDMARK_NAMES and "right_wrist" in LANDMARK_NAMES


def test_no_person_frame_returns_none():
    est = PoseEstimator(view="face_on")
    blank = np.zeros((300, 200, 3), dtype=np.uint8)  # solid black, no person
    assert est.estimate(blank) is None
    est.close()


@requires_video
def test_pose_on_real_face_on_frame_returns_pixel_landmarks():
    src = VideoFileSource(TEST_VIDEO, split=0.5)
    est = PoseEstimator(view="face_on")
    found = None
    seen = 0
    for s in src.frames():
        crop = s.view_crops[C.VIEW_FACE_ON]
        lms = est.estimate(crop)
        seen += 1
        if lms is not None:
            found = (crop, lms)
            break
        if seen >= 60:   # a person should be visible within the first ~2s
            break
    src.close()
    est.close()
    assert found is not None, "expected pose on at least one early face-on frame"
    crop, lms = found
    assert len(lms) == 33
    h, w = crop.shape[:2]
    # landmarks are in PIXELS of the crop, in range
    for lm in lms:
        assert -1.0 <= lm.x <= w + 1.0
        assert -1.0 <= lm.y <= h + 1.0
        assert 0.0 <= lm.visibility <= 1.0
    names = {lm.name for lm in lms}
    assert "left_wrist" in names and "left_shoulder" in names
