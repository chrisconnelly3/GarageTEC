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
