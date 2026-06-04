import numpy as np
from metrics.context import MetricContext
from metrics.defs import rotation_3d as r3
from store.models import Landmark3D


def _ctx(pose3d, moments):
    return MetricContext(swing_id=1, player=None, ppi=0.0, fps=30.0,
                         _pose={}, _moment_frame=moments, pose_3d=pose3d)


def _shoulders(turn_deg):
    th = np.radians(turn_deg)
    # shoulder line in ground plane, rotated `turn_deg` about +Y from +X
    L = np.array([np.cos(th), 1.4, np.sin(th)])
    R = -L + np.array([0, 2.8, 0])     # mirror across center, same height
    return [Landmark3D("left_shoulder", *L, 0.9),
            Landmark3D("right_shoulder", *R, 0.9)]


def _hips(turn_deg):
    th = np.radians(turn_deg)
    L = np.array([0.5 * np.cos(th), 0.9, 0.5 * np.sin(th)])
    R = -L + np.array([0, 1.8, 0])
    return [Landmark3D("left_hip", *L, 0.9), Landmark3D("right_hip", *R, 0.9)]


def test_shoulder_turn_3d_relative_to_address():
    pose3d = {0: _shoulders(0) + _hips(0),       # address
              40: _shoulders(85) + _hips(45)}    # top
    moments = {("face_on", "address"): 0, ("face_on", "top"): 40}
    ctx = _ctx(pose3d, moments)
    out = {m.name + "@" + m.context: m for m in r3.shoulder_turn(ctx)}
    assert abs(abs(out["shoulder_turn_deg@top"].value) - 85.0) < 1.0
    assert out["shoulder_turn_deg@top"].method.startswith("triangulated_3d")


def test_x_factor_is_shoulder_minus_hip_at_top():
    pose3d = {0: _shoulders(0) + _hips(0), 40: _shoulders(85) + _hips(45)}
    moments = {("face_on", "address"): 0, ("face_on", "top"): 40}
    ctx = _ctx(pose3d, moments)
    xf = {m.context: m for m in r3.x_factor(ctx)}
    assert abs(abs(xf["top"].value) - 40.0) < 1.5


def test_rotation_3d_noops_without_pose_3d():
    ctx = _ctx({}, {("face_on", "top"): 40})
    assert r3.shoulder_turn(ctx) == []
    assert r3.x_factor(ctx) == []
