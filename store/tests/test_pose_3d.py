# store/tests/test_pose_3d.py
# (the `db` fixture is provided by store/tests/conftest.py -> in-memory init_db)
from store import repo
from store.models import Landmark3D


def _swing(db):
    pid = repo.get_or_create_player(db, "T", 70.0, "R").id
    sid = repo.create_session(db, pid).id
    return repo.add_swing(db, sid, pid, "v.MOV").id


def test_save_get_clear_pose_3d_frames(db):
    swing_id = _swing(db)
    frames = {
        10: [Landmark3D("left_shoulder", 0.2, 1.4, 0.0, 0.99),
             Landmark3D("right_shoulder", -0.2, 1.4, 0.0, 0.98)],
        11: [Landmark3D("left_shoulder", 0.21, 1.4, 0.02, 0.97)],
    }
    n = repo.save_pose_3d_frames(db, swing_id, frames)
    assert n == 2
    got = repo.get_pose_3d_frames(db, swing_id)
    assert set(got.keys()) == {10, 11}
    lm = got[10][0]
    assert lm.name == "left_shoulder"
    assert abs(lm.x - 0.2) < 1e-9 and abs(lm.confidence - 0.99) < 1e-9
    assert repo.clear_pose_3d_frames(db, swing_id) == 2
    assert repo.get_pose_3d_frames(db, swing_id) == {}
