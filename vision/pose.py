"""MediaPipe BlazePose wrapper. One PoseEstimator instance per view. Converts a
BGR crop into a list[Landmark] with PIXEL x,y (of the crop), normalized z, and
visibility. Returns None when no pose is detected (e.g. empty/no-person frame).
"""
from typing import List, Optional

import cv2
import mediapipe as mp

from vision import constants as C
from store.models import Landmark

# MediaPipe Pose 33-landmark names, in landmark-index order.
LANDMARK_NAMES = [
    "nose", "left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner",
    "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left",
    "mouth_right", "left_shoulder", "right_shoulder", "left_elbow",
    "right_elbow", "left_wrist", "right_wrist", "left_pinky", "right_pinky",
    "left_index", "right_index", "left_thumb", "right_thumb", "left_hip",
    "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle",
    "left_heel", "right_heel", "left_foot_index", "right_foot_index",
]


class PoseEstimator:
    def __init__(self, view: str):
        self.view = view
        self._pose = mp.solutions.pose.Pose(
            static_image_mode=False,
            model_complexity=C.POSE_MODEL_COMPLEXITY,
            min_detection_confidence=C.POSE_MIN_DET_CONF,
            min_tracking_confidence=C.POSE_MIN_TRK_CONF,
        )

    def estimate(self, bgr) -> Optional[List[Landmark]]:
        h, w = bgr.shape[:2]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        result = self._pose.process(rgb)
        if result.pose_landmarks is None:
            return None
        out: List[Landmark] = []
        for i, lm in enumerate(result.pose_landmarks.landmark):
            out.append(Landmark(
                name=LANDMARK_NAMES[i],
                x=lm.x * w,        # normalized -> pixels of the crop
                y=lm.y * h,
                z=lm.z,            # roughly metric-normalized depth (kept as-is)
                visibility=lm.visibility,
            ))
        return out

    def close(self) -> None:
        self._pose.close()


def make_pose_estimator(view: str, backend: str = None):
    """Return a pose estimator for `view`. backend: "mediapipe" (BlazePose, this
    module's PoseEstimator) or "rtmpose" (vision.pose_rtm.RTMPoseEstimator).
    Defaults to constants.POSE_BACKEND. Both share the estimate()/close() API and
    return Landmark lists keyed by the same names the metrics use."""
    backend = backend or C.POSE_BACKEND
    if backend == "rtmpose":
        from vision.pose_rtm import RTMPoseEstimator
        return RTMPoseEstimator(view=view)
    return PoseEstimator(view=view)
