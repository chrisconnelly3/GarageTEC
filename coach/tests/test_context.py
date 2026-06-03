from coach import context


def test_build_swing_context_metrics_and_shot(db, seeded):
    ctx = context.build_swing_context(db, seeded["swing_id"])

    assert ctx["swing_id"] == seeded["swing_id"]
    assert ctx["player"]["height_in"] == 72.0
    assert ctx["player"]["handedness"] == "R"
    assert ctx["club"] == "7i"

    # Matched shot surfaced from the linked shot row.
    assert ctx["shot"] is not None
    assert ctx["shot"]["ball_speed"] == 119.0
    assert ctx["shot"]["carry"] == 172.0

    # Metrics present, keyed by (name, context).
    metrics = {(m["name"], m["context"]): m for m in ctx["metrics"]}
    hip = metrics[("hip_sway_in", "impact")]
    assert hip["value"] == 2.6
    assert hip["unit"] == "in"
    assert hip["method"] == "shoulder_ratio_0.24"

    # Baseline = median of the two prior values (1.3, 1.5) = 1.4; current above it.
    assert abs(hip["baseline"] - 1.4) < 1e-9
    assert hip["history_n"] == 2
    assert hip["vs_baseline_delta"] > 0  # 2.6 vs 1.4

    # Norms comparison attached (hip_sway_in is confidence:none -> history only).
    assert hip["norms"]["use_history_only"] is True


def test_build_swing_context_no_shot(db, seeded):
    # Unlink the shot; context.shot should be None but metrics still build.
    from store import repo
    repo.unlink_shot(db, seeded["swing_id"])
    ctx = context.build_swing_context(db, seeded["swing_id"])
    assert ctx["shot"] is None
    assert len(ctx["metrics"]) == 2


def test_build_session_context_lists_swings(db, seeded):
    ctx = context.build_session_context(db, seeded["session_id"])
    assert ctx["session_id"] == seeded["session_id"]
    # 2 prior + 1 target swing seeded in this session.
    assert ctx["swing_count"] == 3
    assert len(ctx["swings"]) == 3
    assert all("metrics" in s for s in ctx["swings"])
