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


def _swing_from_row(r):
    return Swing(id=r["id"], session_id=r["session_id"], player_id=r["player_id"],
                 created_at=r["created_at"], source_video_path=r["source_video_path"],
                 view_layout=r["view_layout"], fps=r["fps"], width=r["width"],
                 height=r["height"], club=r["club"], notes=r["notes"],
                 shot_id=r["shot_id"])


def add_swing(conn, session_id, player_id, source_video_path, *, view_layout=None,
              fps=None, width=None, height=None, club=None, notes=None):
    ts = dbmod.now_iso()
    cur = conn.execute(
        "INSERT INTO swing(session_id, player_id, created_at, source_video_path, "
        "view_layout, fps, width, height, club, notes) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (session_id, player_id, ts, source_video_path, view_layout, fps, width,
         height, club, notes))
    conn.commit()
    return _swing_from_row(conn.execute(
        "SELECT * FROM swing WHERE id=?", (cur.lastrowid,)).fetchone())


def get_swing(conn, swing_id):
    row = conn.execute("SELECT * FROM swing WHERE id=?", (swing_id,)).fetchone()
    return _swing_from_row(row) if row else None


def list_swings(conn, session_id=None, limit=None):
    sql = "SELECT * FROM swing"
    args = []
    if session_id is not None:
        sql += " WHERE session_id=?"
        args.append(session_id)
    sql += " ORDER BY id"
    if limit is not None:
        sql += " LIMIT ?"
        args.append(limit)
    return [_swing_from_row(r) for r in conn.execute(sql, args).fetchall()]


_SHOT_COLS = [
    "swing_id", "player_id", "session_id", "captured_at", "device_id",
    "shot_number", "ball_speed", "total_spin", "spin_axis", "hla", "vla",
    "carry", "club_speed", "attack_angle", "club_path", "face_to_target",
    "raw_json",
]


def save_shot(conn, shot: Shot):
    vals = [getattr(shot, c) for c in _SHOT_COLS]
    placeholders = ",".join("?" * len(_SHOT_COLS))
    cur = conn.execute(
        f"INSERT INTO shot({','.join(_SHOT_COLS)}) VALUES ({placeholders})", vals)
    conn.commit()
    shot.id = cur.lastrowid
    return shot


def link_shot_to_swing(conn, shot_id, swing_id):
    conn.execute("UPDATE shot SET swing_id=? WHERE id=?", (swing_id, shot_id))
    conn.execute("UPDATE swing SET shot_id=? WHERE id=?", (shot_id, swing_id))
    conn.commit()


def _landmarks_to_json(landmarks):
    return json.dumps([[lm.name, lm.x, lm.y, lm.z, lm.visibility]
                       for lm in landmarks])


def _landmarks_from_json(text):
    return [Landmark(n, x, y, z, v) for (n, x, y, z, v) in json.loads(text)]


def save_pose_frames(conn, swing_id, view, frames):
    rows = [(swing_id, view, f.frame_index, f.time_s,
             _landmarks_to_json(f.landmarks), f.source) for f in frames]
    conn.executemany(
        "INSERT OR REPLACE INTO pose_frame(swing_id, view, frame_index, time_s, "
        "landmarks_json, source) VALUES (?,?,?,?,?,?)", rows)
    conn.commit()
    return len(rows)


def get_pose_frames(conn, swing_id, view):
    rows = conn.execute(
        "SELECT * FROM pose_frame WHERE swing_id=? AND view=? "
        "ORDER BY frame_index", (swing_id, view)).fetchall()
    return [PoseFrame(id=r["id"], swing_id=r["swing_id"], view=r["view"],
                      frame_index=r["frame_index"], time_s=r["time_s"],
                      landmarks=_landmarks_from_json(r["landmarks_json"]),
                      source=r["source"]) for r in rows]
