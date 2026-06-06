# store/tests/test_calibration.py   (uses the `db` fixture from conftest.py)
from store import repo


def test_save_activate_and_get_active(db):
    c1 = repo.save_calibration(db, device_index=0, cols=9, rows=6,
                               square_mm=25.0, n_poses=22, reprojection_error=0.41,
                               calib_json='{"image_width": 640}')
    assert repo.get_active_calibration(db).id == c1.id        # newest is active
    c2 = repo.save_calibration(db, device_index=0, cols=9, rows=6,
                               square_mm=25.0, n_poses=30, reprojection_error=0.3,
                               calib_json='{"image_width": 641}')
    assert repo.get_active_calibration(db).id == c2.id        # newest active now
    assert len(repo.list_calibrations(db)) == 2
    repo.set_active_calibration(db, c1.id)                    # re-activate older
    active = repo.get_active_calibration(db)
    assert active.id == c1.id and active.is_active == 1


def test_get_active_none_when_empty(db):
    assert repo.get_active_calibration(db) is None


def test_set_active_bad_id_returns_none_and_preserves_active(db):
    """Fix 1: a nonexistent cal_id must NOT clear the currently active cal."""
    c1 = repo.save_calibration(db, device_index=0, cols=9, rows=6,
                               square_mm=25.0, n_poses=22, reprojection_error=0.41,
                               calib_json='{}')
    # sanity: c1 is active
    assert repo.get_active_calibration(db).id == c1.id

    # attempt to activate a nonexistent id
    result = repo.set_active_calibration(db, 99999)
    assert result is None

    # c1 must STILL be active
    still_active = repo.get_active_calibration(db)
    assert still_active is not None and still_active.id == c1.id
