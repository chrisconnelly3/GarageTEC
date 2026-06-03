from store import repo
from store.models import Shot, Moment
from sync.service import SyncService


def _swing(db, pid, sid, path="v.MOV"):
    return repo.add_swing(db, sid, pid, path)


def _shot(db, pid, sid, captured_at):
    return repo.save_shot(db, Shot(captured_at=captured_at, player_id=pid,
                                   session_id=sid))


def test_propose_matches_pairs_by_order_without_applying(ctx):
    db, pid, sid = ctx
    sw1 = _swing(db, pid, sid)
    sw2 = _swing(db, pid, sid)
    sh1 = _shot(db, pid, sid, "2026-06-03T00:00:01+00:00")
    sh2 = _shot(db, pid, sid, "2026-06-03T00:00:05+00:00")

    svc = SyncService(db)
    props = svc.propose_matches(session_id=sid, player_id=pid)

    pairs = {(p.swing_id, p.shot_id) for p in props}
    assert pairs == {(sw1.id, sh1.id), (sw2.id, sh2.id)}
    # propose must NOT apply links
    assert repo.get_swing(db, sw1.id).shot_id is None
    assert repo.get_swing(db, sw2.id).shot_id is None


def test_auto_reconcile_links_confident_and_returns_rest(ctx):
    db, pid, sid = ctx
    # 3 swings, 3 shots; all order-aligned. With no aligned times, confidence is
    # the order-only base (0.6) which is BELOW the default 0.75 threshold, so a
    # default-threshold auto_reconcile applies nothing and returns 3 proposals.
    sws = [_swing(db, pid, sid) for _ in range(3)]
    shs = [_shot(db, pid, sid, f"2026-06-03T00:00:0{i}+00:00") for i in range(3)]

    svc = SyncService(db)
    result = svc.auto_reconcile(session_id=sid, player_id=pid)
    assert result["linked"] == []
    assert len(result["proposals"]) == 3
    for sw in sws:
        assert repo.get_swing(db, sw.id).shot_id is None

    # Lower the threshold so the order-only pairs auto-link.
    svc_loose = SyncService(db, threshold=0.5)
    result2 = svc_loose.auto_reconcile(session_id=sid, player_id=pid)
    assert len(result2["linked"]) == 3
    assert result2["proposals"] == []
    linked_shot_ids = {repo.get_swing(db, sw.id).shot_id for sw in sws}
    assert linked_shot_ids == {sh.id for sh in shs}


def _swing_with_impact(db, pid, sid, impact_s):
    sw = repo.add_swing(db, pid and sid and sid, pid, "v.MOV") if False else \
        repo.add_swing(db, sid, pid, "v.MOV")
    repo.save_moments(db, sw.id, [Moment(sw.id, "impact", "face_on", 100, impact_s)])
    return sw


def test_aligned_times_make_order_pairs_auto_linkable(ctx):
    db, pid, sid = ctx
    # impact times (relative s) increase with order; shot captured_at increases
    # with order too -> consistent -> service grants a time bonus.
    sw1 = _swing_with_impact(db, pid, sid, 2.0)
    sw2 = _swing_with_impact(db, pid, sid, 9.0)
    sh1 = _shot(db, pid, sid, "2026-06-03T00:00:02+00:00")
    sh2 = _shot(db, pid, sid, "2026-06-03T00:00:09+00:00")

    svc = SyncService(db)  # default threshold 0.75
    result = svc.auto_reconcile(session_id=sid, player_id=pid)
    assert len(result["linked"]) == 2  # time bonus pushed both over 0.75
    assert repo.get_swing(db, sw1.id).shot_id == sh1.id
    assert repo.get_swing(db, sw2.id).shot_id == sh2.id


def test_multi_user_no_cross_player_link(db):
    # Two players in the SAME session window, overlapping in time.
    p1 = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    p2 = repo.get_or_create_player(db, "Brother", 70.0, "R").id
    s1 = repo.create_session(db, p1).id
    s2 = repo.create_session(db, p2).id

    sw1 = repo.add_swing(db, s1, p1, "chris.MOV")
    sw2 = repo.add_swing(db, s2, p2, "brother.MOV")
    # brother's shot is captured first in wall-clock, but belongs to p2/s2
    sh_brother = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:01+00:00",
                                         player_id=p2, session_id=s2))
    sh_chris = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:02+00:00",
                                       player_id=p1, session_id=s1))

    svc = SyncService(db, threshold=0.5)  # loose so order pairs would link
    svc.auto_reconcile(session_id=s1, player_id=p1)
    svc.auto_reconcile(session_id=s2, player_id=p2)

    # Chris's swing must link ONLY to Chris's shot, never the brother's.
    assert repo.get_swing(db, sw1.id).shot_id == sh_chris.id
    assert repo.get_swing(db, sw2.id).shot_id == sh_brother.id


def test_cross_session_same_player_not_matched(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    s_old = repo.create_session(db, pid).id
    s_new = repo.create_session(db, pid).id
    old_swing = repo.add_swing(db, s_old, pid, "old.MOV")
    new_shot = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:01+00:00",
                                       player_id=pid, session_id=s_new))
    svc = SyncService(db, threshold=0.5)
    svc.auto_reconcile(session_id=s_new, player_id=pid)
    # the old session's swing is out of scope -> stays unmatched
    assert repo.get_swing(db, old_swing.id).shot_id is None
    assert repo.list_unmatched_shots(db, session_id=s_new) != []


def test_apply_match_and_unlink(ctx):
    db, pid, sid = ctx
    sw = _swing(db, pid, sid)
    sh = _shot(db, pid, sid, "2026-06-03T00:00:01+00:00")
    svc = SyncService(db)

    svc.apply_match(swing_id=sw.id, shot_id=sh.id)
    assert repo.get_swing(db, sw.id).shot_id == sh.id
    row = db.execute("SELECT swing_id FROM shot WHERE id=?", (sh.id,)).fetchone()
    assert row["swing_id"] == sw.id
    # now matched -> not in unmatched lists
    assert repo.list_unmatched_swings(db, session_id=sid) == []

    svc.unlink(swing_id=sw.id)
    assert repo.get_swing(db, sw.id).shot_id is None
    assert [s.id for s in repo.list_unmatched_swings(db, session_id=sid)] == [sw.id]
    assert [s.id for s in repo.list_unmatched_shots(db, session_id=sid)] == [sh.id]
