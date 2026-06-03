from store import repo


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_add_get_list_swing(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "golf swing.MOV",
                        view_layout="side_by_side_LR", fps=29.98,
                        width=1920, height=1080, club="7i")
    assert sw.id is not None
    got = repo.get_swing(db, sw.id)
    assert got.source_video_path == "golf swing.MOV" and got.player_id == pid
    assert [s.id for s in repo.list_swings(db, session_id=sid)] == [sw.id]
