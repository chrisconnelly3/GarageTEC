from coach import prompt


def _ctx():
    return {
        "kind": "swing", "swing_id": 1, "club": "7i",
        "player": {"height_in": 72.0, "handedness": "R"},
        "shot": {"ball_speed": 119.0, "carry": 172.0},
        "metrics": [
            {"name": "hip_sway_in", "context": "impact", "value": 2.6,
             "unit": "in", "baseline": 1.4,
             "norms": {"use_history_only": True}},
        ],
    }


def _valid_output():
    return {
        "headline": "Hips slide a touch toward target at impact.",
        "findings": [
            {"metric": "hip_sway_in", "context": "impact", "value": 2.6,
             "unit": "in", "vs_baseline": "+1.2 in vs your 1.4 norm",
             "vs_ideal": None, "ball_effect": "fits the slight pull",
             "severity": "medium"},
        ],
        "drills": [{"name": "Wall drill", "why": "limit sway", "how": "..."}],
        "confidence_notes": ["hip sway is a 2D estimate"],
    }


def test_build_user_includes_real_numbers():
    user = prompt.build_user(_ctx())
    assert "hip_sway_in" in user
    assert "2.6" in user
    assert "119.0" in user  # shot ball speed grounded in the prompt


def test_schema_is_object_with_required_keys():
    schema = prompt.OUTPUT_SCHEMA
    assert schema["type"] == "object"
    for key in ("headline", "findings", "drills", "confidence_notes"):
        assert key in schema["properties"]


def test_validate_accepts_canonical_output():
    ok, errors = prompt.validate(_valid_output(), _ctx())
    assert ok is True
    assert errors == []


def test_schema_declares_optional_summary():
    schema = prompt.OUTPUT_SCHEMA
    assert "summary" in schema["properties"]
    assert "summary" not in schema["required"]


def test_build_user_asks_for_summary():
    user = prompt.build_user(_ctx())
    assert "summary" in user


def test_validate_accepts_output_with_summary():
    out = _valid_output()
    out["summary"] = ("Strong strike: your hip sway at impact runs a touch "
                      "ahead of your norm, which fits the slight pull you saw.")
    ok, errors = prompt.validate(out, _ctx())
    assert ok is True
    assert errors == []


def test_validate_rejects_non_string_summary():
    out = _valid_output()
    out["summary"] = 123  # must be a string when present
    ok, errors = prompt.validate(out, _ctx())
    assert ok is False
    assert any("summary" in e for e in errors)


def test_summary_does_not_relax_findings_grounding():
    # A rich summary must NOT excuse an ungrounded finding.
    bad = _valid_output()
    bad["summary"] = "A beautifully sequenced move from the ground up."
    bad["findings"][0]["metric"] = "made_up_metric"
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("made_up_metric" in e for e in errors)


def test_validate_rejects_missing_top_level_key():
    bad = _valid_output()
    del bad["drills"]
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("drills" in e for e in errors)


def test_validate_rejects_finding_citing_unknown_metric():
    bad = _valid_output()
    bad["findings"][0]["metric"] = "made_up_metric"
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("made_up_metric" in e for e in errors)


def test_validate_rejects_finding_with_wrong_value():
    bad = _valid_output()
    bad["findings"][0]["value"] = 9.9  # not the real 2.6
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("value" in e for e in errors)


def test_validate_rejects_finding_without_any_comparison():
    bad = _valid_output()
    bad["findings"][0]["vs_baseline"] = None
    bad["findings"][0]["vs_ideal"] = None
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("comparison" in e for e in errors)


def test_validate_rejects_value_from_wrong_context():
    # Grounding has two phases of the same metric with different values; a
    # finding may not cite a value that only belongs to the OTHER phase.
    ctx = _ctx()
    ctx["metrics"] = [
        {"name": "hip_sway_in", "context": "top", "value": 3.9, "unit": "in"},
        {"name": "hip_sway_in", "context": "impact", "value": 1.6, "unit": "in"},
    ]
    bad = _valid_output()
    # cite impact but with the TOP value (3.9) -> must be rejected
    bad["findings"][0]["context"] = "impact"
    bad["findings"][0]["value"] = 3.9
    ok, errors = prompt.validate(bad, ctx)
    assert ok is False
    assert any("does not match" in e for e in errors)
    # the correctly-keyed value passes
    good = _valid_output()
    good["findings"][0]["context"] = "impact"
    good["findings"][0]["value"] = 1.6
    ok2, errors2 = prompt.validate(good, ctx)
    assert ok2 is True and errors2 == []


def test_validate_rejects_finding_in_unknown_context():
    bad = _valid_output()
    bad["findings"][0]["context"] = "finish"  # metric exists, not at finish
    ok, errors = prompt.validate(bad, _ctx())
    assert ok is False
    assert any("unknown context" in e for e in errors)


def test_validate_rejects_non_dict():
    ok, errors = prompt.validate(["not", "a", "dict"], _ctx())
    assert ok is False
    assert errors
