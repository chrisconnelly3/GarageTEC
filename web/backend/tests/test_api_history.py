from store import repo
from store.models import Metric
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
