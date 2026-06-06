from store import repo
from store.models import Metric, Shot
from store import db as dbmod
from web.backend.tests.conftest import seed_player


def _swing(conn, pid):
    sid = repo.get_open_session(conn, pid)
    sid = sid.id if sid else repo.create_session(conn, pid).id
    return repo.add_swing(conn, sid, pid, "v.mp4").id


def test_history_returns_ordered_points(client, conn):
    p = seed_player(conn)
    s1 = _swing(conn, p.id)
    s2 = _swing(conn, p.id)
    repo.save_metrics(conn, s1, [Metric(s1, "hip_sway_in", "impact", 2.0, "in", "m")])
    repo.save_metrics(conn, s2, [Metric(s2, "hip_sway_in", "impact", 3.0, "in", "m")])

    r = client.get("/api/history", params={"player": p.id,
                                           "metric": "hip_sway_in",
                                           "context": "impact"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert [pt["value"] for pt in points] == [2.0, 3.0]
    assert points[0]["swing_id"] == s1 and "created_at" in points[0]


def test_history_defaults_context_overall(client, conn):
    p = seed_player(conn)
    s1 = _swing(conn, p.id)
    repo.save_metrics(conn, s1, [Metric(s1, "tempo", "overall", 3.1, "ratio", "m")])
    r = client.get("/api/history", params={"player": p.id, "metric": "tempo"})
    assert [pt["value"] for pt in r.json()["points"]] == [3.1]


def _shot(conn, pid, *, at, **kw):
    sess = repo.get_open_session(conn, pid)
    sid = sess.id if sess else repo.create_session(conn, pid).id
    return repo.save_shot(conn, Shot(captured_at=at, player_id=pid,
                                     session_id=sid, **kw))


def test_ball_history_shape_and_target(client, conn):
    p = seed_player(conn)
    _shot(conn, p.id, at="2026-06-03T00:00:01+00:00", ball_speed=150.0,
          club="Driver")
    _shot(conn, p.id, at="2026-06-03T00:00:02+00:00", ball_speed=160.0,
          club="Driver")
    r = client.get("/api/ball-history", params={"player": p.id,
                                                "metric": "ball_speed",
                                                "club": "Driver"})
    assert r.status_code == 200
    body = r.json()
    assert body["player"] == p.id and body["metric"] == "ball_speed"
    assert body["club"] == "Driver"
    assert body["target"] == 167   # TrackMan Driver ball_speed
    assert [pt["value"] for pt in body["points"]] == [150.0, 160.0]
    assert {"shot_id", "captured_at", "value"} <= set(body["points"][0])


def test_ball_history_null_target_without_club(client, conn):
    p = seed_player(conn)
    _shot(conn, p.id, at="t1", ball_speed=150.0)
    body = client.get("/api/ball-history",
                      params={"player": p.id, "metric": "ball_speed"}).json()
    assert body["club"] is None and body["target"] is None
    assert [pt["value"] for pt in body["points"]] == [150.0]


def test_ball_history_rejects_bad_metric(client, conn):
    p = seed_player(conn)
    r = client.get("/api/ball-history",
                   params={"player": p.id, "metric": "raw_json"})
    assert r.status_code == 400


# ---- Fix 4: body-metric allowlist on /api/history --------------------------

def test_history_rejects_unknown_metric(client, conn):
    p = seed_player(conn)
    r = client.get("/api/history",
                   params={"player": p.id, "metric": "raw_json"})
    assert r.status_code == 400


def test_history_rejects_invalid_context(client, conn):
    p = seed_player(conn)
    r = client.get("/api/history",
                   params={"player": p.id, "metric": "hip_sway_in",
                           "context": "badphase"})
    assert r.status_code == 400


def test_history_allows_valid_metric_and_context(client, conn):
    p = seed_player(conn)
    r = client.get("/api/history",
                   params={"player": p.id, "metric": "hip_sway_in",
                           "context": "impact"})
    assert r.status_code == 200
