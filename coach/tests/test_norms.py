from coach import norms


def test_load_norms_has_meta_disclaimer():
    data = norms.load_norms()
    assert "_meta" in data
    assert "curated" in data["_meta"]["status"].lower() or \
           "human" in data["_meta"]["note"].lower()


def test_in_range_value():
    data = {"hip_sway_in": {"range": [0.0, 1.5], "units": "in",
                            "source": "example", "confidence": "low"}}
    r = norms.compare("hip_sway_in", 1.0, norms=data)
    assert r["in_range"] is True
    assert r["delta"] == 0.0
    assert r["confidence"] == "low"
    assert r["source"] == "example"


def test_above_range_value_reports_positive_delta():
    data = {"hip_sway_in": {"range": [0.0, 1.5], "units": "in",
                            "source": "example", "confidence": "low"}}
    r = norms.compare("hip_sway_in", 2.6, norms=data)
    assert r["in_range"] is False
    assert abs(r["delta"] - 1.1) < 1e-9   # 2.6 - 1.5 upper bound
    assert r["direction"] == "above"


def test_below_range_value_reports_negative_delta():
    data = {"x": {"range": [10.0, 20.0], "units": "deg",
                  "source": "ex", "confidence": "medium"}}
    r = norms.compare("x", 7.0, norms=data)
    assert r["in_range"] is False
    assert abs(r["delta"] - (-3.0)) < 1e-9  # 7 - 10 lower bound
    assert r["direction"] == "below"


def test_confidence_none_falls_back_to_history():
    data = {"rough_metric": {"range": [], "units": "deg",
                             "source": None, "confidence": "none"}}
    r = norms.compare("rough_metric", 42.0, norms=data)
    assert r["confidence"] == "none"
    assert r["in_range"] is None       # no ideal to compare against
    assert r["use_history_only"] is True


def test_unknown_metric_is_history_only():
    r = norms.compare("not_in_dataset", 5.0, norms={})
    assert r["confidence"] == "none"
    assert r["in_range"] is None
    assert r["use_history_only"] is True
