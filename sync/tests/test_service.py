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
