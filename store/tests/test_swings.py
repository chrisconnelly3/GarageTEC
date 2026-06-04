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


def test_list_swing_summaries_enriches(db):
    import json
    from store.models import Metric, Coaching
    p = repo.get_or_create_player(db, "Sum", 70.0, "R")
    sid = repo.create_session(db, p.id).id
    sw = repo.add_swing(db, sid, p.id, "a.mp4", club="7i")
    repo.save_metrics(db, sw.id, [
        Metric(sw.id, "hip_sway_in", "impact", 2.5, "in", "ratio"),
        Metric(sw.id, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
    ])
    rows = repo.list_swing_summaries(db, player_id=p.id, session_id=sid, limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == sw.id and r["club"] == "7i"
    assert r["has_shot"] is False
    # a key metric surfaced (hip_sway impact)
    assert r["hip_sway_in"] == 2.5


def test_latest_ready_swing_picks_newest_with_metric_and_coaching(db):
    import json
    from store.models import Metric, Coaching
    p = repo.get_or_create_player(db, "L", 70.0, "R")
    sid = repo.create_session(db, p.id).id
    repo.add_swing(db, sid, p.id, "a.mp4")          # no metric/coaching
    ready = repo.add_swing(db, sid, p.id, "b.mp4")
    repo.save_metrics(db, ready.id, [Metric(ready.id, "hip_sway_in", "impact", 2.5, "in", "ratio")])
    repo.save_coaching(db, Coaching(swing_id=ready.id, session_id=None, kind="swing",
                                    content_json=json.dumps({"headline": "x"}), model="m"))
    got = repo.latest_ready_swing(db, p.id)
    assert got is not None and got.id == ready.id
    assert repo.latest_ready_swing(db, p.id, session_id=sid + 99) is None
