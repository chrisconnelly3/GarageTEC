from store import repo
from store.models import Landmark, PoseFrame


def _swing(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return repo.add_swing(db, sid, pid, "v.MOV").id


def test_pose_frames_roundtrip(db):
    sw = _swing(db)
    frames = [
        PoseFrame(swing_id=sw, view="face_on", frame_index=i, time_s=i / 30.0,
                  landmarks=[Landmark("nose", 10.0 + i, 20.0, 0.1, 0.95),
                             Landmark("left_shoulder", 5.0, 15.0, 0.2, 0.9)])
        for i in range(3)
    ]
    n = repo.save_pose_frames(db, sw, "face_on", frames)
    assert n == 3
    loaded = repo.get_pose_frames(db, sw, "face_on")
    assert [f.frame_index for f in loaded] == [0, 1, 2]  # ordered
    assert loaded[1].landmarks[0].name == "nose"
    assert abs(loaded[1].landmarks[0].x - 11.0) < 1e-9
    assert loaded[0].source == "mediapipe_pose"
