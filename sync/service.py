"""Sync service: bridges the store to the pure matcher and applies links.

Always scoped to a single (player_id, session_id) — the multi-user-safety
guarantee. Never matches across players or sessions.
"""

from store import repo
from sync.matcher import SwingCandidate, ShotCandidate, propose, MatchProposal

DEFAULT_THRESHOLD = 0.75
DEFAULT_TIME_WINDOW_S = 4.0


class SyncService:
    def __init__(self, conn, *, threshold: float = DEFAULT_THRESHOLD,
                 time_window_s: float = DEFAULT_TIME_WINDOW_S):
        self.conn = conn
        self.threshold = threshold
        self.time_window_s = time_window_s

    # ---- candidate loading -------------------------------------------------

    def _swing_candidates(self, session_id, player_id):
        swings = repo.list_unmatched_swings(self.conn, session_id=session_id,
                                            player_id=player_id)
        out = []
        for order, sw in enumerate(swings):
            out.append(SwingCandidate(swing_id=sw.id, order=order,
                                      impact_time=self._impact_time(sw.id)))
        return out

    def _shot_candidates(self, session_id, player_id):
        shots = repo.list_unmatched_shots(self.conn, session_id=session_id,
                                          player_id=player_id)
        return [ShotCandidate(shot_id=sh.id, order=order,
                              captured_at=sh.captured_at)
                for order, sh in enumerate(shots)]

    def _impact_time(self, swing_id):
        """Swing impact wall-clock proxy: the impact moment's time_s, or None.

        time_s is relative to the recording; absolute alignment to the shot
        clock is unavailable in the current store, so the matcher uses this only
        as a tie-break/refinement and degrades to order-only when it cannot be
        aligned (see _aligned_candidates)."""
        for m in repo.get_moments(self.conn, swing_id):
            if m.kind == "impact":
                return m.time_s
        return None

    # ---- proposals ---------------------------------------------------------

    def propose_matches(self, *, session_id, player_id) -> list[MatchProposal]:
        swings = self._swing_candidates(session_id, player_id)
        shots = self._shot_candidates(session_id, player_id)
        return propose(swings, shots, time_window_s=self.time_window_s)

    def auto_reconcile(self, *, session_id, player_id) -> dict:
        """Apply links for proposals at/above threshold; return both lists.

        Returns {"linked": [MatchProposal...], "proposals": [MatchProposal...]}.
        Conservative: anything below threshold is left for the UI, never forced.
        """
        proposals = self.propose_matches(session_id=session_id,
                                         player_id=player_id)
        linked, rest = [], []
        for p in proposals:
            if p.confidence >= self.threshold:
                repo.link_shot_to_swing(self.conn, p.shot_id, p.swing_id)
                linked.append(p)
            else:
                rest.append(p)
        return {"linked": linked, "proposals": rest}
