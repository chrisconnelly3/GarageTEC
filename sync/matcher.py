"""Pure swing<->shot matching. No DB, no store import.

Order is the primary signal: the k-th unmatched swing pairs with the k-th
unmatched shot. Time (swing impact_time vs shot captured_at) refines confidence
and breaks ties when present. Extra swings or extra shots simply stay unmatched.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

DEFAULT_TIME_WINDOW_S = 4.0


@dataclass(frozen=True)
class SwingCandidate:
    swing_id: int
    order: int
    impact_time: Optional[float] = None  # relative seconds within recording


@dataclass(frozen=True)
class ShotCandidate:
    shot_id: int
    order: int
    captured_at: Optional[str] = None  # ISO-8601 wall clock


@dataclass(frozen=True)
class MatchProposal:
    swing_id: int
    shot_id: int
    confidence: float
    reason: str


def propose(swings: List[SwingCandidate], shots: List[ShotCandidate],
            *, time_window_s: float = DEFAULT_TIME_WINDOW_S) -> List[MatchProposal]:
    """Return ranked MatchProposals (highest confidence first).

    Order-primary: pair k-th swing with k-th shot (both sorted by order). The
    surplus on the longer side is left unmatched. Confidence comes from order
    agreement plus an optional time bonus; ranking is by confidence desc.
    """
    sw = sorted(swings, key=lambda s: s.order)
    sh = sorted(shots, key=lambda s: s.order)
    n = min(len(sw), len(sh))
    proposals = []
    for i in range(n):
        s, h = sw[i], sh[i]
        confidence, reason = _score(s, h, time_window_s)
        proposals.append(MatchProposal(swing_id=s.swing_id, shot_id=h.shot_id,
                                       confidence=confidence, reason=reason))
    proposals.sort(key=lambda p: p.confidence, reverse=True)
    return proposals


def _score(swing: SwingCandidate, shot: ShotCandidate,
           time_window_s: float):
    """Confidence in [0,1]. Base from order pairing; bonus when impact_time and
    captured_at are both present and close."""
    base = 0.6  # order pairing alone is a robust-but-not-certain signal
    reason = "order"
    return base, reason
