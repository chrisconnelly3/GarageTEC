from metrics.context import MetricContext
from store.models import Landmark3D


def test_pose_3d_at_resolves_moment_frame():
    ctx = MetricContext(
        swing_id=1, player=None, ppi=0.0, fps=30.0,
        _pose={}, _moment_frame={("face_on", "top"): 40, ("down_line", "top"): 40},
        pose_3d={40: [Landmark3D("left_shoulder", 0.2, 1.4, 0.0, 0.9)]},
    )
    pose = ctx.pose_3d_at("top")
    assert pose is not None and pose[0].name == "left_shoulder"
    assert ctx.pose_3d_at("impact") is None    # no moment / no 3d frame
