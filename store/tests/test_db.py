def test_init_creates_tables_and_version(db):
    names = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"player", "session", "swing", "shot", "pose_frame",
            "moment", "metric", "media", "schema_version"} <= names
    assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 1


def test_models_construct():
    from store.models import Player, Shot, Landmark, PoseFrame
    p = Player(name="Chris", height_in=72.0, handedness="R")
    assert p.id is None and p.height_in == 72.0
    s = Shot(captured_at="t", ball_speed=148.2)
    assert s.swing_id is None and s.ball_speed == 148.2
    pf = PoseFrame(swing_id=1, view="face_on", frame_index=0, time_s=0.0,
                   landmarks=[Landmark("nose", 1.0, 2.0, 0.0, 0.9)])
    assert pf.landmarks[0].name == "nose"
