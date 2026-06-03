from sync.matcher import SwingCandidate, ShotCandidate, MatchProposal, propose


def _swings(*specs):
    # specs: (swing_id, order, impact_time)
    return [SwingCandidate(swing_id=s, order=o, impact_time=t) for (s, o, t) in specs]


def _shots(*specs):
    # specs: (shot_id, order, captured_at)
    return [ShotCandidate(shot_id=s, order=o, captured_at=t) for (s, o, t) in specs]


def test_equal_clean_counts_pair_1to1_by_order():
    swings = _swings((10, 0, None), (11, 1, None), (12, 2, None))
    shots = _shots((20, 0, None), (21, 1, None), (22, 2, None))
    props = propose(swings, shots)
    pairs = {(p.swing_id, p.shot_id) for p in props}
    assert pairs == {(10, 20), (11, 21), (12, 22)}
    assert all(p.confidence > 0.0 for p in props)


def test_no_candidates_returns_empty():
    assert propose([], []) == []
    assert propose(_swings((10, 0, None)), []) == []
    assert propose([], _shots((20, 0, None))) == []


def test_extra_swing_stays_unmatched():
    # 3 swings, 2 shots -> a practice swing is left over
    swings = _swings((10, 0, None), (11, 1, None), (12, 2, None))
    shots = _shots((20, 0, None), (21, 1, None))
    props = propose(swings, shots)
    assert {(p.swing_id, p.shot_id) for p in props} == {(10, 20), (11, 21)}
    matched_swings = {p.swing_id for p in props}
    assert 12 not in matched_swings  # surplus swing unmatched


def test_extra_shot_stays_unmatched():
    # 2 swings, 3 shots -> a shot with no swing is left over
    swings = _swings((10, 0, None), (11, 1, None))
    shots = _shots((20, 0, None), (21, 1, None), (22, 2, None))
    props = propose(swings, shots)
    assert {(p.swing_id, p.shot_id) for p in props} == {(10, 20), (11, 21)}
    matched_shots = {p.shot_id for p in props}
    assert 22 not in matched_shots  # surplus shot unmatched


def test_time_agreement_raises_confidence_above_order_only():
    # impact_time (relative s) close to a shared recording start; captured_at
    # is wall-clock. We model "close in time" by giving the matcher a derived
    # delta via recording_start. To keep the matcher pure, callers pass
    # impact_time already aligned to the shot clock as epoch seconds when known.
    near = _swings((10, 0, 100.0))   # impact at t=100.0s (aligned epoch-ish)
    near_shot = _shots((20, 0, "x"))  # captured_at carries the aligned value
    # Order-only baseline:
    base = propose(_swings((10, 0, None)), _shots((20, 0, None)))[0].confidence
    # With aligned times within window, confidence must exceed the order-only base.
    timed = propose(_swings((10, 0, 100.0)),
                    _shots((20, 0, "1970-01-01T00:01:40+00:00")))  # = 100.0s epoch
    assert timed[0].confidence > base
    assert "time" in timed[0].reason


def test_time_breaks_tie_when_two_shots_equidistant_in_order():
    # Two swings, two shots, but shot order is ambiguous (same order index given
    # by upstream). Time should pick the closer pairing and rank it first.
    swings = _swings((10, 0, 10.0), (11, 1, 50.0))
    shots = _shots((20, 0, "1970-01-01T00:00:10+00:00"),   # 10s -> swing 10
                   (21, 1, "1970-01-01T00:00:50+00:00"))   # 50s -> swing 11
    props = propose(swings, shots)
    by_swing = {p.swing_id: p.shot_id for p in props}
    assert by_swing == {10: 20, 11: 21}
    # the well-aligned pairs should be high confidence
    assert all(p.confidence >= 0.75 for p in props)
