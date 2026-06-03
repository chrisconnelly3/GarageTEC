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
    captured_at are both present and within the window (smaller delta -> larger
    bonus). Falls back to order-only when either time is missing/unparseable."""
    base = 0.6
    delta = _time_delta_s(swing.impact_time, shot.captured_at)
    if delta is None:
        return base, "order"
    if delta > time_window_s:
        # times disagree -> trust order but flag the disagreement
        return base, f"order; time_delta={delta:.2f}s>window"
    # within window: linearly scale a bonus up to +0.4 as delta -> 0
    bonus = 0.4 * (1.0 - (delta / time_window_s))
    confidence = min(1.0, base + bonus)
    return confidence, f"order+time; delta={delta:.2f}s"


def _time_delta_s(impact_time, captured_at):
    """Absolute seconds between an aligned impact_time (float epoch-or-relative
    seconds) and a shot captured_at (ISO-8601 string or float seconds). Returns
    None if either is missing or unparseable."""
    if impact_time is None or captured_at is None:
        return None
    shot_s = _to_seconds(captured_at)
    if shot_s is None:
        return None
    try:
        return abs(float(impact_time) - shot_s)
    except (TypeError, ValueError):
        return None


def _to_seconds(value):
    """Coerce a captured_at to seconds. Accepts a float/int (already seconds) or
    an ISO-8601 timestamp (converted to POSIX seconds)."""
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return datetime.fromisoformat(value).timestamp()
    except (TypeError, ValueError):
        return None
