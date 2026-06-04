import json
from datetime import datetime, timedelta, timezone
from store import db as dbmod
from store.models import (
    Player, Session, Swing, Shot, Landmark, PoseFrame, Moment, Metric, Media,
    Coaching,
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


def get_player(conn, player_id):
    row = conn.execute("SELECT * FROM player WHERE id=?", (player_id,)).fetchone()
    if row is None:
        return None
    return Player(id=row["id"], name=row["name"], height_in=row["height_in"],
                  handedness=row["handedness"], created_at=row["created_at"])


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


def _session_from_row(r):
    return Session(id=r["id"], player_id=r["player_id"],
                   started_at=r["started_at"], ended_at=r["ended_at"],
                   location=r["location"], notes=r["notes"])


def get_session(conn, session_id):
    row = conn.execute("SELECT * FROM session WHERE id=?",
                       (session_id,)).fetchone()
    return _session_from_row(row) if row else None


def list_sessions(conn, player_id=None):
    sql = "SELECT * FROM session"
    args = []
    if player_id is not None:
        sql += " WHERE player_id=?"
        args.append(player_id)
    sql += " ORDER BY id DESC"
    return [_session_from_row(r) for r in conn.execute(sql, args).fetchall()]


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


def latest_ready_swing(conn, player_id, session_id=None):
    """Newest swing for a player that has >=1 metric AND >=1 coaching row.
    Optionally scoped to a session. Returns a Swing or None."""
    sql = (
        "SELECT sw.* FROM swing sw "
        "WHERE sw.player_id=? "
        "  AND EXISTS (SELECT 1 FROM metric m WHERE m.swing_id=sw.id) "
        "  AND EXISTS (SELECT 1 FROM coaching c WHERE c.swing_id=sw.id) ")
    args = [player_id]
    if session_id is not None:
        sql += "AND sw.session_id=? "
        args.append(session_id)
    sql += "ORDER BY sw.id DESC LIMIT 1"
    row = conn.execute(sql, args).fetchone()
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


def save_moments(conn, swing_id, moments):
    conn.executemany(
        "INSERT INTO moment(swing_id, kind, view, frame_index, time_s) "
        "VALUES (?,?,?,?,?)",
        [(swing_id, m.kind, m.view, m.frame_index, m.time_s) for m in moments])
    conn.commit()
    return len(moments)


def get_moments(conn, swing_id):
    rows = conn.execute("SELECT * FROM moment WHERE swing_id=? ORDER BY frame_index",
                        (swing_id,)).fetchall()
    return [Moment(id=r["id"], swing_id=r["swing_id"], kind=r["kind"],
                   view=r["view"], frame_index=r["frame_index"], time_s=r["time_s"])
            for r in rows]


def save_metrics(conn, swing_id, metrics):
    ts = dbmod.now_iso()
    conn.executemany(
        "INSERT INTO metric(swing_id, name, context, value, unit, method, "
        "created_at) VALUES (?,?,?,?,?,?,?)",
        [(swing_id, m.name, m.context, m.value, m.unit, m.method, ts)
         for m in metrics])
    conn.commit()
    return len(metrics)


def get_metrics(conn, swing_id):
    rows = conn.execute("SELECT * FROM metric WHERE swing_id=? ORDER BY id",
                        (swing_id,)).fetchall()
    return [Metric(id=r["id"], swing_id=r["swing_id"], name=r["name"],
                   context=r["context"], value=r["value"], unit=r["unit"],
                   method=r["method"], created_at=r["created_at"]) for r in rows]


def clear_metrics(conn, swing_id):
    cur = conn.execute("DELETE FROM metric WHERE swing_id=?", (swing_id,))
    conn.commit()
    return cur.rowcount


def swing_history(conn, player_id, metric_name, context="overall"):
    rows = conn.execute(
        "SELECT sw.id, sw.created_at, m.value "
        "FROM metric m JOIN swing sw ON sw.id = m.swing_id "
        "WHERE sw.player_id=? AND m.name=? AND m.context=? "
        "ORDER BY sw.created_at", (player_id, metric_name, context)).fetchall()
    return [(r["id"], r["created_at"], r["value"]) for r in rows]


def save_media(conn, media: Media):
    cur = conn.execute(
        "INSERT INTO media(swing_id, kind, path, meta_json) VALUES (?,?,?,?)",
        (media.swing_id, media.kind, media.path, media.meta_json))
    conn.commit()
    media.id = cur.lastrowid
    return media


def get_media(conn, swing_id):
    rows = conn.execute("SELECT * FROM media WHERE swing_id=? ORDER BY id",
                        (swing_id,)).fetchall()
    return [Media(id=r["id"], swing_id=r["swing_id"], kind=r["kind"],
                  path=r["path"], meta_json=r["meta_json"]) for r in rows]


def _shot_from_row(r):
    return Shot(id=r["id"], swing_id=r["swing_id"], player_id=r["player_id"],
                session_id=r["session_id"], captured_at=r["captured_at"],
                device_id=r["device_id"], shot_number=r["shot_number"],
                ball_speed=r["ball_speed"], total_spin=r["total_spin"],
                spin_axis=r["spin_axis"], hla=r["hla"], vla=r["vla"],
                carry=r["carry"], club_speed=r["club_speed"],
                attack_angle=r["attack_angle"], club_path=r["club_path"],
                face_to_target=r["face_to_target"], raw_json=r["raw_json"])


def get_shot(conn, shot_id):
    row = conn.execute("SELECT * FROM shot WHERE id=?", (shot_id,)).fetchone()
    return _shot_from_row(row) if row else None


def _filtered(sql, session_id, player_id):
    clauses, args = [], []
    if session_id is not None:
        clauses.append("session_id=?"); args.append(session_id)
    if player_id is not None:
        clauses.append("player_id=?"); args.append(player_id)
    if clauses:
        sql += " AND " + " AND ".join(clauses)
    return sql, args


def list_unmatched_swings(conn, session_id=None, player_id=None):
    sql, args = _filtered("SELECT * FROM swing WHERE shot_id IS NULL",
                          session_id, player_id)
    return [_swing_from_row(r) for r in conn.execute(sql + " ORDER BY id", args)]


def list_unmatched_shots(conn, session_id=None, player_id=None):
    sql, args = _filtered("SELECT * FROM shot WHERE swing_id IS NULL",
                          session_id, player_id)
    return [_shot_from_row(r) for r in conn.execute(sql + " ORDER BY id", args)]


def unlink_shot(conn, swing_id):
    row = conn.execute("SELECT shot_id FROM swing WHERE id=?", (swing_id,)).fetchone()
    conn.execute("UPDATE swing SET shot_id=NULL WHERE id=?", (swing_id,))
    if row and row["shot_id"] is not None:
        conn.execute("UPDATE shot SET swing_id=NULL WHERE id=?", (row["shot_id"],))
    conn.commit()


def save_coaching(conn, c):
    ts = c.created_at or dbmod.now_iso()
    cur = conn.execute(
        "INSERT INTO coaching(swing_id, session_id, kind, content_json, model, "
        "created_at) VALUES (?,?,?,?,?,?)",
        (c.swing_id, c.session_id, c.kind, c.content_json, c.model, ts))
    conn.commit()
    c.id, c.created_at = cur.lastrowid, ts
    return c


def get_coaching(conn, swing_id=None, session_id=None):
    if swing_id is not None:
        rows = conn.execute("SELECT * FROM coaching WHERE swing_id=? ORDER BY id",
                            (swing_id,)).fetchall()
    elif session_id is not None:
        rows = conn.execute("SELECT * FROM coaching WHERE session_id=? ORDER BY id",
                            (session_id,)).fetchall()
    else:
        rows = conn.execute("SELECT * FROM coaching ORDER BY id").fetchall()
    return [Coaching(id=r["id"], swing_id=r["swing_id"], session_id=r["session_id"],
                     kind=r["kind"], content_json=r["content_json"],
                     model=r["model"], created_at=r["created_at"]) for r in rows]
