from store import repo
from store.models import Shot
from store import db as dbmod
from web.backend.tests.conftest import seed_player


def _unmatched_pair(conn, player):
    sid = repo.create_session(conn, player.id).id
    swing = repo.add_swing(conn, sid, player.id, "v.mp4")
    shot = repo.save_shot(conn, Shot(captured_at=dbmod.now_iso(),
                                     player_id=player.id, session_id=sid))
    return sid, swing, shot


def test_proposals_lists_candidate_for_session(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    r = client.get("/api/sync/proposals", params={"session": sid})
    assert r.status_code == 200
    body = r.json()
    props = body["proposals"]
    assert any(pr["swing_id"] == swing.id and pr["shot_id"] == shot.id
               for pr in props)
    assert "confidence" in props[0] and "reason" in props[0]
    assert swing.id in [s["id"] for s in body["unmatched_swings"]]
    assert shot.id in [s["id"] for s in body["unmatched_shots"]]


def test_apply_links_swing_to_shot(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    r = client.post("/api/sync/apply",
                    json={"swing_id": swing.id, "shot_id": shot.id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert repo.get_swing(conn, swing.id).shot_id == shot.id


def test_unlink_clears_link(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    repo.link_shot_to_swing(conn, shot.id, swing.id)
    r = client.post("/api/sync/unlink", json={"swing_id": swing.id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert repo.get_swing(conn, swing.id).shot_id is None


# ---- Fix 6b: 404 for nonexistent ids ---------------------------------------

def test_apply_nonexistent_swing_returns_404(client, conn):
    p = seed_player(conn)
    sid, _, shot = _unmatched_pair(conn, p)
    r = client.post("/api/sync/apply",
                    json={"swing_id": 99999, "shot_id": shot.id})
    assert r.status_code == 404


def test_apply_nonexistent_shot_returns_404(client, conn):
    p = seed_player(conn)
    sid, swing, _ = _unmatched_pair(conn, p)
    r = client.post("/api/sync/apply",
                    json={"swing_id": swing.id, "shot_id": 99999})
    assert r.status_code == 404


def test_unlink_nonexistent_swing_returns_404(client, conn):
    r = client.post("/api/sync/unlink", json={"swing_id": 99999})
    assert r.status_code == 404
