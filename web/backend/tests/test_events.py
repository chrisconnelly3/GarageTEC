import json

from store import repo
from store.models import Metric, Coaching
from web.backend.events import SwingWatcher
from web.backend.tests.conftest import seed_player, seed_ready_swing


def _bare_swing(conn, pid):
    sid = repo.get_open_session(conn, pid)
    sid = sid.id if sid else repo.create_session(conn, pid).id
    return repo.add_swing(conn, sid, pid, "v.mp4").id


def _make_ready(conn, swing_id):
    repo.save_metrics(conn, swing_id,
                      [Metric(swing_id, "tempo", "overall", 3.0, "r", "m")])
    repo.save_coaching(conn, Coaching(swing_id=swing_id, session_id=None,
                                      kind="swing",
                                      content_json=json.dumps({"headline": "ok"})))


def test_watcher_emits_only_ready_swings_once(conn):
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    watcher = SwingWatcher(conn)

    first = watcher.poll()
    assert [e["swing_id"] for e in first] == [ready.id]
    # second poll with no new ready swings -> nothing
    assert watcher.poll() == []


def test_watcher_skips_not_yet_ready_then_emits_when_ready(conn):
    p = seed_player(conn)
    pending = _bare_swing(conn, p.id)  # metrics/coaching not written yet
    watcher = SwingWatcher(conn)
    assert watcher.poll() == []  # not ready -> not emitted

    _make_ready(conn, pending)
    assert [e["swing_id"] for e in watcher.poll()] == [pending]


def test_events_endpoint_streams_swing_ready(client, conn):
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    # one-shot mode: ?once=1 polls a single time and closes (test-friendly)
    r = client.get("/events", params={"once": 1})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: swing_ready" in r.text
    assert f'"swing_id": {ready.id}' in r.text
