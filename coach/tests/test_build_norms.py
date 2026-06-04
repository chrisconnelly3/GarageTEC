import math

from coach.norms import build_norms as b


def test_clean_drops_inf_nan_and_none():
    raw = [10.0, float("inf"), float("-inf"), float("nan"), None, 12.0]
    out = b.clean_values(raw)
    assert out == [10.0, 12.0]


def test_clean_drops_exact_clamp_artifacts():
    raw = [0.0, 5.0, 180.0, 7.0, 0.0]
    out = b.clean_values(raw, drop_clamps=(0.0, 180.0))
    assert out == [5.0, 7.0]


def test_clean_winsorizes_extreme_outliers_inward():
    # 100 values 1..100; a stray 100000 should be clipped down to the p99 of
    # the surviving set (not deleted), and the tiny -100000 clipped up to p1.
    raw = [float(i) for i in range(1, 101)] + [100000.0, -100000.0]
    out = b.clean_values(raw)
    assert max(out) < 200.0          # huge outlier pulled in
    assert min(out) > -50.0          # huge negative pulled in
    assert len(out) == 102           # winsorize clips, does not drop rows


def test_clean_empty_returns_empty():
    assert b.clean_values([]) == []
    assert b.clean_values([float("nan"), None]) == []
