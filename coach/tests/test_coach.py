import json

import pytest

from coach import coach
from coach.backend import FakeBackend
from coach import context as context_mod
from store import repo


def _valid_for(ctx):
    m = ctx["metrics"][0]
    return {
        "headline": "Hips slide toward target at impact.",
        "findings": [{
            "metric": m["name"], "context": m["context"], "value": m["value"],
            "unit": m["unit"], "vs_baseline": "above your norm",
            "vs_ideal": None, "ball_effect": "slight pull", "severity": "medium",
        }],
        "drills": [{"name": "Wall drill", "why": "limit sway", "how": "..."}],
        "confidence_notes": ["hip sway is a 2D estimate"],
    }


def test_coach_swing_persists_valid_coaching(db, seeded):
    ctx = context_mod.build_swing_context(db, seeded["swing_id"])
    backend = FakeBackend(canned=_valid_for(ctx))

    result = coach.coach_swing(db, backend, seeded["swing_id"])

    assert result.id is not None
    assert result.kind == "swing"
    assert result.model == "fake"
    rows = repo.get_coaching(db, swing_id=seeded["swing_id"])
    assert len(rows) == 1
    stored = json.loads(rows[0].content_json)
    assert stored["findings"][0]["metric"] == ctx["metrics"][0]["name"]
    # The backend was called with the system prompt + a user prompt of real nums.
    assert len(backend.calls) == 1
    assert "hip_sway_in" in backend.calls[0][1]


def test_coach_swing_rejects_malformed_and_persists_nothing(db, seeded):
    # Finding cites a metric not in context -> validation fails.
    bad = {
        "headline": "x",
        "findings": [{"metric": "made_up", "value": 1.0,
                      "vs_baseline": "x"}],
        "drills": [], "confidence_notes": [],
    }
    backend = FakeBackend(canned=bad)

    with pytest.raises(coach.CoachingValidationError):
        coach.coach_swing(db, backend, seeded["swing_id"])

    assert repo.get_coaching(db, swing_id=seeded["swing_id"]) == []


def test_coach_swing_rejects_missing_key_and_persists_nothing(db, seeded):
    backend = FakeBackend(canned={"headline": "only this"})
    with pytest.raises(coach.CoachingValidationError):
        coach.coach_swing(db, backend, seeded["swing_id"])
    assert repo.get_coaching(db, swing_id=seeded["swing_id"]) == []


def test_coach_session_persists_session_coaching(db, seeded):
    sctx = context_mod.build_session_context(db, seeded["session_id"])
    # Cite a metric from the first swing that has metrics.
    metric = next(m for sw in sctx["swings"] for m in sw["metrics"])
    canned = {
        "headline": "Session: sway trending up.",
        "findings": [{"metric": metric["name"], "context": metric["context"],
                      "value": metric["value"], "unit": metric["unit"],
                      "vs_baseline": "up over the session", "vs_ideal": None,
                      "severity": "medium"}],
        "drills": [{"name": "Wall drill"}],
        "confidence_notes": [],
    }
    backend = FakeBackend(canned=canned)

    result = coach.coach_session(db, backend, seeded["session_id"])
    assert result.kind == "session"
    rows = repo.get_coaching(db, session_id=seeded["session_id"])
    assert len(rows) == 1


def test_cli_run_swing_with_injected_backend(db, seeded, capsys):
    from coach import run
    ctx = context_mod.build_swing_context(db, seeded["swing_id"])
    backend = FakeBackend(canned=_valid_for(ctx))

    code = run._run(["--swing", str(seeded["swing_id"])], conn=db, backend=backend)
    assert code == 0
    out = capsys.readouterr().out
    assert "headline" in out.lower() or "Hips" in out
    assert len(repo.get_coaching(db, swing_id=seeded["swing_id"])) == 1


def test_cli_requires_a_target(db):
    from coach import run
    with pytest.raises(SystemExit):
        run._run([], conn=db, backend=FakeBackend(canned={}))
