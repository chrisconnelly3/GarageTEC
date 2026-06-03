import json
from datetime import datetime, timedelta, timezone
from store import db as dbmod
from store.models import (
    Player, Session, Swing, Shot, Landmark, PoseFrame, Moment, Metric, Media,
)


def get_or_create_player(conn, name, height_in, handedness):
    row = conn.execute("SELECT * FROM player WHERE name=?", (name,)).fetchone()
    if row is not None:
        return Player(id=row["id"], name=row["name"], height_in=row["height_in"],
                      handedness=row["handedness"], created_at=row["created_at"])
    ts = dbmod.now_iso()
    cur = conn.execute(
        "INSERT INTO player(name, height_in, handedness, created_at) "
        "VALUES (?,?,?,?)", (name, height_in, handedness, ts))
    conn.commit()
    return Player(id=cur.lastrowid, name=name, height_in=height_in,
                  handedness=handedness, created_at=ts)


def list_players(conn):
    rows = conn.execute("SELECT * FROM player ORDER BY name").fetchall()
    return [Player(id=r["id"], name=r["name"], height_in=r["height_in"],
                   handedness=r["handedness"], created_at=r["created_at"])
            for r in rows]


def create_session(conn, player_id, location=None, notes=None):
    ts = dbmod.now_iso()
    cur = conn.execute(
        "INSERT INTO session(player_id, started_at, location, notes) "
        "VALUES (?,?,?,?)", (player_id, ts, location, notes))
    conn.commit()
    return Session(id=cur.lastrowid, player_id=player_id, started_at=ts,
                   location=location, notes=notes)


def end_session(conn, session_id):
    conn.execute("UPDATE session SET ended_at=? WHERE id=?",
                 (dbmod.now_iso(), session_id))
    conn.commit()


def get_open_session(conn, player_id):
    row = conn.execute(
        "SELECT * FROM session WHERE player_id=? AND ended_at IS NULL "
        "ORDER BY id DESC LIMIT 1", (player_id,)).fetchone()
    if row is None:
        return None
    return Session(id=row["id"], player_id=row["player_id"],
                   started_at=row["started_at"], ended_at=row["ended_at"],
                   location=row["location"], notes=row["notes"])


def end_idle_sessions(conn, idle_minutes):
    """Close open sessions whose most-recent shot (or start) is older than
    idle_minutes. Returns count closed."""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=idle_minutes)).isoformat()
    rows = conn.execute(
        "SELECT s.id, "
        "COALESCE(MAX(sh.captured_at), s.started_at) AS last_activity "
        "FROM session s LEFT JOIN shot sh ON sh.session_id = s.id "
        "WHERE s.ended_at IS NULL GROUP BY s.id").fetchall()
    closed = 0
    for r in rows:
        if (r["last_activity"] or "") < cutoff:
            end_session(conn, r["id"])
            closed += 1
    return closed
