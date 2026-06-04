# metrics/tests/test_sidebend_3d.py
import math
import numpy as np
from metrics.context import MetricContext
from metrics.defs import sidebend_3d as s3
from store.models import Landmark3D


def _ctx(pose3d, moments):
    return MetricContext(swing_id=1, player=None, ppi=0.0, fps=30.0,
                         _pose={}, _moment_frame=moments, pose_3d=pose3d)


def test_shoulder_tilt_3d_at_impact_known_angle():
    th = math.radians(36)
    L = np.array([math.cos(th), 1.4 + math.sin(th), 0.0])
    R = np.array([-math.cos(th), 1.4 - math.sin(th), 0.0])
    pose = [Landmark3D("left_shoulder", *L, 0.9),
            Landmark3D("right_shoulder", *R, 0.9)]
    ctx = _ctx({50: pose}, {("face_on", "impact"): 50})
    out = {m.context: m for m in s3.shoulder_tilt_3d(ctx)}
    assert abs(out["impact"].value - 36.0) < 1.0
    assert out["impact"].method.startswith("triangulated_3d")
    assert "address" not in out          # 3D side-bend only at top/impact


def test_sidebend_3d_noops_without_pose_3d():
    ctx = _ctx({}, {("face_on", "impact"): 50})
    assert s3.shoulder_tilt_3d(ctx) == []
