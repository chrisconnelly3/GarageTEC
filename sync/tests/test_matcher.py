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
