"""Active-player state + per-player auto session resolution.

Holds which player is currently hitting. For each captured shot it stamps the
shot with the active player's id and the player's open session (resuming it if
one is open, else creating a new one). A periodic sweep closes sessions idle
longer than idle_minutes, so a player who returns within the window resumes the
same session, while a long gap starts a fresh one.

Uses store.repo exclusively. The connection captured at construction is used for
player lookups; attribute()/sweep_idle() take an explicit connection so the
manager works against an in-memory store in tests.
"""
from store import db as dbmod
from store import repo
from store.models import Shot


class SessionManager:
    def __init__(self, conn, idle_minutes: int = 15):
        self._conn = conn
        self.idle_minutes = idle_minutes
        self.active_player = None

    # ---- active player ----------------------------------------------------
    def set_active_player(self, name, height_in, handedness):
        """Select (creating if needed) the player who is now hitting."""
        self.active_player = repo.get_or_create_player(
            self._conn, name, height_in, handedness)
        return self.active_player

    def roster(self, conn=None):
        return repo.list_players(conn or self._conn)

    # ---- attribution ------------------------------------------------------
    def attribute(self, conn, shot: Shot) -> Shot:
        """Stamp shot.player_id + shot.session_id for the active player,
        opening or resuming the player's session. Refreshes captured_at.
        Persists nothing (persist.py saves)."""
        if self.active_player is None:
            raise RuntimeError("no active player selected")
        pid = self.active_player.id
        session = repo.get_open_session(conn, pid) or repo.create_session(conn, pid)
        shot.player_id = pid
        shot.session_id = session.id
        shot.captured_at = dbmod.now_iso()
        return shot

    def sweep_idle(self, conn) -> int:
        """Close sessions idle longer than idle_minutes. Returns count closed."""
        return repo.end_idle_sessions(conn, self.idle_minutes)
