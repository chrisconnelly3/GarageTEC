"""Triangulate the two synced per-view 2D pose timelines into a metric 3D
timeline. Frames are assumed synchronized (composite source), so face_on.frames[i]
and down_line.frames[i] are the same instant.
"""
from typing import List, Optional

import cv2
import numpy as np

from store.models import Landmark, Landmark3D
from vision.threed.types import Pose3DTimeline

MIN_VISIBILITY = 0.5


def triangulate_point(P1, P2, pt1, pt2):
    """DLT triangulation of one correspondence. Returns 3D np.array (meters)."""
    a = np.array(pt1, dtype=float).reshape(2, 1)
    b = np.array(pt2, dtype=float).reshape(2, 1)
    Xh = cv2.triangulatePoints(np.asarray(P1, float), np.asarray(P2, float), a, b)
    return (Xh[:3] / Xh[3]).ravel()


def _by_name(frame: Optional[List[Landmark]]):
    return {l.name: l for l in frame} if frame else {}


def reconstruct(face_on, down_line, calibration,
                min_visibility: float = MIN_VISIBILITY) -> Pose3DTimeline:
    """Per composite frame, triangulate every landmark visible (>= min_visibility)
    in BOTH views. Confidence = min of the two visibilities. Frames with no
    triangulated landmark become an empty list."""
    P1, P2 = calibration.projection_matrices()
    out = Pose3DTimeline()
    n = min(len(face_on), len(down_line))
    for i in range(n):
        fo, dl = _by_name(face_on.frames[i]), _by_name(down_line.frames[i])
        lms3d: List[Landmark3D] = []
        for name in fo.keys() & dl.keys():
            a, b = fo[name], dl[name]
            if a.visibility < min_visibility or b.visibility < min_visibility:
                continue
            X = triangulate_point(P1, P2, (a.x, a.y), (b.x, b.y))
            lms3d.append(Landmark3D(name=name, x=float(X[0]), y=float(X[1]),
                                    z=float(X[2]),
                                    confidence=float(min(a.visibility,
                                                         b.visibility))))
        out.times_s.append(face_on.times_s[i] if i < len(face_on.times_s) else 0.0)
        out.frames.append(lms3d)
    return out
