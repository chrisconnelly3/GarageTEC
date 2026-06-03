"""Fixtures for the metrics brain tests.

`db` is a fresh in-memory store (mirrors store/tests/conftest.py).
`seed_swing` builds a synthetic swing: a player, a session, a swing, pose
frames for both views, and address/top/impact moments. Pose frames are built
from hand-authored landmark dicts so each metric has known geometry.
"""
import pytest

from store import db as dbmod
from store import repo
from store.models import Landmark, PoseFrame, Moment


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


def make_frame(swing_id, view, frame_index, coords, *, time_s=None):
    """coords: {name: (x, y)} -> a PoseFrame with z=0, visibility=1.0."""
    lms = [Landmark(name=n, x=float(x), y=float(y), z=0.0, visibility=1.0)
           for n, (x, y) in coords.items()]
    return PoseFrame(swing_id=swing_id, view=view, frame_index=frame_index,
                     time_s=time_s if time_s is not None else frame_index / 30.0,
                     landmarks=lms)


def seed_swing(db, *, height_in=72.0,
               face_on_frames=None, down_line_frames=None,
               moments=None):
    """Insert a complete synthetic swing. Returns the swing id.

    *_frames: list[(frame_index, {name: (x, y)})].
    moments: list[(kind, view, frame_index)].
    """
    pid = repo.get_or_create_player(db, "Synth", height_in, "R").id
    sid = repo.create_session(db, pid).id
    sw = repo.add_swing(db, sid, pid, "synthetic.MOV",
                        view_layout="side_by_side_LR", fps=30.0,
                        width=1920, height=1080).id
    if face_on_frames:
        repo.save_pose_frames(db, sw, "face_on", [
            make_frame(sw, "face_on", idx, coords) for idx, coords in face_on_frames])
    if down_line_frames:
        repo.save_pose_frames(db, sw, "down_line", [
            make_frame(sw, "down_line", idx, coords) for idx, coords in down_line_frames])
    if moments:
        repo.save_moments(db, sw, [
            Moment(sw, kind, view, idx, idx / 30.0)
            for (kind, view, idx) in moments])
    return sw
