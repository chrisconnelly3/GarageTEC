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


def test_percentiles_basic():
    vals = [float(i) for i in range(1, 101)]  # 1..100
    p10, med, p90 = b.percentiles(vals)
    assert abs(p10 - 10.9) < 0.5
    assert abs(med - 50.5) < 0.5
    assert abs(p90 - 90.1) < 0.5


def test_percentiles_empty_is_none():
    assert b.percentiles([]) is None


def test_convert_none_is_identity():
    assert b.convert(11.16, "none") == 11.16


def test_convert_vertical_from_horizontal():
    # CaddieSet spine 70.53 deg vs horizontal -> 19.47 deg vs vertical (ours)
    assert abs(b.convert(70.53, "vertical_from_horizontal") - 19.47) < 1e-9
