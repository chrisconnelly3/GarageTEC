def test_init_creates_tables_and_version(db):
    names = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"player", "session", "swing", "shot", "pose_frame",
            "moment", "metric", "media", "schema_version"} <= names
    assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 1
