from store import repo


def test_get_settings_returns_defaults_when_empty(db):
    s = repo.get_settings(db)
    assert s == {"idle_minutes": 15, "units": "yards", "port": 921}


def test_save_settings_upserts_and_merges(db):
    repo.save_settings(db, {"idle_minutes": 30, "port": 922})
    s = repo.get_settings(db)
    assert s["idle_minutes"] == 30 and s["port"] == 922
    assert s["units"] == "yards"  # untouched default
    # partial update overwrites only provided keys
    repo.save_settings(db, {"units": "meters"})
    s2 = repo.get_settings(db)
    assert s2 == {"idle_minutes": 30, "units": "meters", "port": 922}


def test_get_settings_coerces_types(db):
    repo.save_settings(db, {"idle_minutes": 12, "port": 5000})
    s = repo.get_settings(db)
    assert isinstance(s["idle_minutes"], int) and isinstance(s["port"], int)
