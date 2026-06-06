import json

from store.models import Player, Session, Swing, Shot, Moment, Metric, Media, Coaching
from web.backend import serializers as ser


def test_player_dict():
    p = Player(id=3, name="Chris", height_in=72.0, handedness="R",
               created_at="2026-06-03T00:00:00+00:00")
    assert ser.player_dict(p) == {
        "id": 3, "name": "Chris", "height_in": 72.0, "handedness": "R",
        "created_at": "2026-06-03T00:00:00+00:00"}


def test_session_dict():
    s = Session(id=1, player_id=3, started_at="t", ended_at=None,
                location="bay", notes=None)
    d = ser.session_dict(s)
    assert d["id"] == 1 and d["player_id"] == 3 and d["location"] == "bay"


def test_metric_and_moment_dicts():
    m = Metric(5, "hip_sway_in", "impact", 2.5, "in", "ratio", "t", id=9)
    assert ser.metric_dict(m) == {
        "id": 9, "swing_id": 5, "name": "hip_sway_in", "context": "impact",
        "value": 2.5, "unit": "in", "method": "ratio", "created_at": "t"}
    mo = Moment(5, "impact", "face_on", 120, 0.5, id=2)
    assert ser.moment_dict(mo)["kind"] == "impact"


def test_coaching_dict_parses_content_json():
    c = Coaching(swing_id=5, session_id=None, kind="swing",
                 content_json=json.dumps({"headline": "hi"}), model="claude",
                 created_at="t", id=1)
    d = ser.coaching_dict(c)
    assert d["content"] == {"headline": "hi"}  # parsed, not a raw string


def test_shot_and_media_dicts():
    sh = Shot(captured_at="t", id=7, ball_speed=148.2, carry=172.0)
    assert ser.shot_dict(sh)["ball_speed"] == 148.2
    md = Media(swing_id=5, kind="annotated_video", path="swings/1/a.mp4", id=4)
    assert ser.media_dict(md) == {"id": 4, "swing_id": 5,
                                  "kind": "annotated_video",
                                  "path": "swings/1/a.mp4", "meta": None}


def test_shot_dict_includes_raw_json():
    """Fix 5: raw_json must be present in shot_dict so ball_reference can use
    explicit BackSpin/SideSpin keys from the monitor payload."""
    raw = '{"BackSpin": 2800, "SideSpin": -300}'
    sh = Shot(captured_at="t", id=7, ball_speed=148.2, raw_json=raw)
    d = ser.shot_dict(sh)
    assert "raw_json" in d, "shot_dict must include raw_json"
    assert d["raw_json"] == raw


def test_shot_dict_raw_json_none_when_absent():
    sh = Shot(captured_at="t", id=8, ball_speed=100.0)
    d = ser.shot_dict(sh)
    assert "raw_json" in d and d["raw_json"] is None
