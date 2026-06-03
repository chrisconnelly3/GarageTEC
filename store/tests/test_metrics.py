from store import repo
from store.models import Moment, Metric, Media


def _swing(db, name="Chris"):
    pid = repo.get_or_create_player(db, name, 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, repo.add_swing(db, sid, pid, "v.MOV").id


def test_moments_and_metrics(db):
    _, sw = _swing(db)
    repo.save_moments(db, sw, [Moment(sw, "address", "face_on", 10, 0.33),
                               Moment(sw, "impact", "face_on", 120, 4.0)])
    kinds = {m.kind for m in repo.get_moments(db, sw)}
    assert kinds == {"address", "impact"}

    repo.save_metrics(db, sw, [
        Metric(sw, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
        Metric(sw, "hip_sway_in", "impact", 2.5, "in", "shoulder_ratio_0.24")])
    got = {(m.name, m.context): m.value for m in repo.get_metrics(db, sw)}
    assert got[("hip_sway_in", "impact")] == 2.5
    assert repo.clear_metrics(db, sw) == 2  # idempotent recompute support
    assert repo.get_metrics(db, sw) == []


def test_swing_history_orders_by_time(db):
    pid, sw1 = _swing(db, "Hist")
    sid = repo.get_open_session(db, pid).id
    sw2 = repo.add_swing(db, sid, pid, "v2.MOV").id
    repo.save_metrics(db, sw1, [Metric(sw1, "hip_sway_in", "impact", 2.0, "in", "m")])
    repo.save_metrics(db, sw2, [Metric(sw2, "hip_sway_in", "impact", 3.0, "in", "m")])
    hist = repo.swing_history(db, pid, "hip_sway_in", context="impact")
    assert [v for (_sid, _ts, v) in hist] == [2.0, 3.0]


def test_media(db):
    _, sw = _swing(db, "Media")
    repo.save_media(db, Media(sw, "annotated_video", "swings/x/annotated.mp4"))
    rows = repo.get_media(db, sw)
    assert rows[0].kind == "annotated_video"
