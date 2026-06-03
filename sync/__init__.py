"""GarageTEC Sync: correlate camera swings with R50 shots within (player, session)."""

from sync.matcher import (  # noqa: F401
    SwingCandidate, ShotCandidate, MatchProposal, propose,
)
