from vision.threed.types import Pose3DTimeline
from store.models import Landmark3D


def test_pose3d_timeline_holds_frames():
    tl = Pose3DTimeline()
    tl.times_s.append(0.0)
    tl.frames.append([Landmark3D("nose", 0.0, 1.6, 0.1, 0.9)])
    tl.times_s.append(0.033)
    tl.frames.append(None)            # a dropped frame
    assert len(tl) == 2
    assert tl.frames[1] is None
    assert tl.frames[0][0].name == "nose"
