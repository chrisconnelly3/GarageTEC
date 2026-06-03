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
        return swings  # raw rows; alignment happens in propose_matches

    def _shot_candidates(self, session_id, player_id):
        return repo.list_unmatched_shots(self.conn, session_id=session_id,
                                         player_id=player_id)

    def _aligned_inputs(self, swings, shots):
        """Build matcher inputs. If every swing has an impact moment AND there is
        at least one shot, align both onto a shared zero-based seconds clock:
          - shot seconds  = captured_at(POSIX) - min(captured_at)
          - swing seconds  = impact_time - min(impact_time), shifted to the same
            zero as the shots so close pairs have small deltas.
        Otherwise pass impact_time=None (order-only)."""
        impacts = [self._impact_time(sw.id) for sw in swings]
        shot_secs = [self._to_posix(sh.captured_at) for sh in shots]
        can_align = (swings and shots
                     and all(t is not None for t in impacts)
                     and all(s is not None for s in shot_secs))

        if can_align:
            base_shot = min(shot_secs)
            base_impact = min(impacts)
            swing_cands = [
                SwingCandidate(swing_id=sw.id, order=i,
                               impact_time=(impacts[i] - base_impact))
                for i, sw in enumerate(swings)
            ]
            shot_cands = [
                ShotCandidate(shot_id=sh.id, order=i,
                              captured_at=(shot_secs[i] - base_shot))
                for i, sh in enumerate(shots)
            ]
        else:
            swing_cands = [SwingCandidate(swing_id=sw.id, order=i, impact_time=None)
                           for i, sw in enumerate(swings)]
            shot_cands = [ShotCandidate(shot_id=sh.id, order=i,
                                        captured_at=sh.captured_at)
                          for i, sh in enumerate(shots)]
        return swing_cands, shot_cands

    @staticmethod
    def _to_posix(captured_at):
        from datetime import datetime
        if captured_at is None:
            return None
        try:
            return datetime.fromisoformat(captured_at).timestamp()
        except (TypeError, ValueError):
            return None

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
        swings = repo.list_unmatched_swings(self.conn, session_id=session_id,
                                            player_id=player_id)
        shots = repo.list_unmatched_shots(self.conn, session_id=session_id,
                                          player_id=player_id)
        swing_cands, shot_cands = self._aligned_inputs(swings, shots)
        return propose(swing_cands, shot_cands, time_window_s=self.time_window_s)

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

    def apply_match(self, *, swing_id, shot_id):
        """Manually link a swing to a shot (UI correction)."""
        repo.link_shot_to_swing(self.conn, shot_id, swing_id)

    def unlink(self, *, swing_id):
        """Manually clear a swing's link (UI correction)."""
        repo.unlink_shot(self.conn, swing_id)
