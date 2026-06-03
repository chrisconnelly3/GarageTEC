from vision.persist import persist_swing
from vision.types import PoseTimeline, SwingWindow
from vision.segment import segment_swing
from vision import constants as C
from store import repo
from store.models import Landmark, PoseFrame, Moment


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def _timeline(view, n, x0=10.0):
    tl = PoseTimeline(view=view)
    for i in range(n):
        tl.times_s.append(i / 30.0)
        tl.frames.append([
            Landmark("left_wrist", x0 + i, 50.0 + (i % 5), 0.0, 0.9),
            Landmark("right_wrist", x0 + 2 + i, 52.0, 0.0, 0.9),
            Landmark("left_shoulder", 30.0, 40.0, 0.0, 0.9),
        ])
    return tl


def test_persist_one_swing_writes_all_rows(db):
    pid, sid = _ctx(db)
    n = 60
    dl = _timeline(C.VIEW_DOWN_LINE, n)
    fo = _timeline(C.VIEW_FACE_ON, n)
    window = SwingWindow(start_index=10, end_index=49, peak_index=30)
    moments = segment_swing(dl, fo, window)

    swing_id = persist_swing(
        db, player_id=pid, session_id=sid, source_video_path="golf swing.MOV",
        fps=30.0, width=1920, height=1080, view_layout=C.VIEW_LAYOUT,
        down_line=dl, face_on=fo, window=window, moments=moments)

    sw = repo.get_swing(db, swing_id)
    assert sw is not None and sw.player_id == pid and sw.view_layout == C.VIEW_LAYOUT
    # pose frames for BOTH views, only the window range [10,49] -> 40 frames each
    dl_rows = repo.get_pose_frames(db, swing_id, C.VIEW_DOWN_LINE)
    fo_rows = repo.get_pose_frames(db, swing_id, C.VIEW_FACE_ON)
    assert len(dl_rows) == 40 and len(fo_rows) == 40
    assert dl_rows[0].frame_index == 10 and dl_rows[-1].frame_index == 49
    # 8 moments
    saved = repo.get_moments(db, swing_id)
    assert [m.kind for m in saved] == list(C.PHASE_ORDER)


def test_persist_two_swings_independent_rows(db):
    pid, sid = _ctx(db)
    dl = _timeline(C.VIEW_DOWN_LINE, 120)
    fo = _timeline(C.VIEW_FACE_ON, 120)
    w1 = SwingWindow(0, 39, 20)
    w2 = SwingWindow(60, 99, 80)
    id1 = persist_swing(db, player_id=pid, session_id=sid,
                        source_video_path="v.MOV", fps=30.0, width=1920,
                        height=1080, view_layout=C.VIEW_LAYOUT, down_line=dl,
                        face_on=fo, window=w1,
                        moments=segment_swing(dl, fo, w1))
    id2 = persist_swing(db, player_id=pid, session_id=sid,
                        source_video_path="v.MOV", fps=30.0, width=1920,
                        height=1080, view_layout=C.VIEW_LAYOUT, down_line=dl,
                        face_on=fo, window=w2,
                        moments=segment_swing(dl, fo, w2))
    assert id1 != id2
    assert len(repo.list_swings(db, session_id=sid)) == 2
    assert len(repo.get_moments(db, id1)) == 8
    assert len(repo.get_moments(db, id2)) == 8
    assert len(repo.get_pose_frames(db, id1, C.VIEW_FACE_ON)) == 40


def test_persist_media_recorded_when_path_given(db):
    pid, sid = _ctx(db)
    dl = _timeline(C.VIEW_DOWN_LINE, 30)
    fo = _timeline(C.VIEW_FACE_ON, 30)
    w = SwingWindow(0, 29, 15)
    swing_id = persist_swing(
        db, player_id=pid, session_id=sid, source_video_path="v.MOV",
        fps=30.0, width=1920, height=1080, view_layout=C.VIEW_LAYOUT,
        down_line=dl, face_on=fo, window=w, moments=segment_swing(dl, fo, w),
        annotated_path="swings/x/annotated.mp4")
    media = repo.get_media(db, swing_id)
    kinds = {m.kind for m in media}
    assert "source_video" in kinds
    assert "annotated_video" in kinds
