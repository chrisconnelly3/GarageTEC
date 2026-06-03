import pytest

from store import repo
from metrics import run as runmod
from metrics.tests.test_compute import _full_swing


def test_swings_missing_metrics_lists_only_uncomputed(db):
    sw1 = _full_swing(db)
    sw2 = _full_swing(db)
    # compute sw1 only
    from metrics.compute import compute_metrics
    compute_metrics(db, sw1)
    missing = runmod.swings_missing_metrics(db)
    assert sw2 in missing and sw1 not in missing


def test_run_swing_computes_one(db):
    sw = _full_swing(db)
    code = runmod.run(db, ["--swing", str(sw)])
    assert code == 0
    assert repo.get_metrics(db, sw)  # non-empty


def test_run_all_missing_computes_all_uncomputed(db):
    sw1 = _full_swing(db)
    sw2 = _full_swing(db)
    code = runmod.run(db, ["--all-missing"])
    assert code == 0
    assert repo.get_metrics(db, sw1)
    assert repo.get_metrics(db, sw2)


def test_run_requires_a_mode(db):
    with pytest.raises(SystemExit):
        runmod.run(db, [])
