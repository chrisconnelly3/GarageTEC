"""Gate test: proves cv2 + mediapipe import and a Pose detector constructs.

If this fails on Python 3.12, STOP and follow the 3.11 fallback in the plan
(Task 1) before doing anything else.
"""


def test_cv2_imports_and_reads_version():
    import cv2
    assert hasattr(cv2, "__version__")
    assert hasattr(cv2, "VideoCapture")


def test_numpy_is_v1_for_mediapipe_abi():
    import numpy as np
    # mediapipe 0.10.x wheels expect the NumPy 1.x ABI.
    assert np.__version__.split(".")[0] == "1"


def test_mediapipe_imports_and_constructs_pose():
    import mediapipe as mp
    pose = mp.solutions.pose.Pose(
        static_image_mode=False,
        model_complexity=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    assert pose is not None
    pose.close()
