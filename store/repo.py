import hashlib
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from store import db as dbmod
from store.models import (
    Player, Session, Swing, Shot, Landmark, Landmark3D, PoseFrame, Moment, Metric, Media,
    Coaching, Calibration,
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


SETTINGS_DEFAULTS = {"idle_minutes": 15, "units": "yards", "port": 921}


def get_settings(conn):
    """Single global settings dict. Missing keys fall back to defaults;
    idle_minutes/port are coerced to int."""
    rows = conn.execute("SELECT key, value FROM settings").fetchall()
    stored = {r["key"]: r["value"] for r in rows}
    out = dict(SETTINGS_DEFAULTS)
    for k in ("idle_minutes", "port"):
        if k in stored and stored[k] is not None:
            try:
                out[k] = int(stored[k])
            except (TypeError, ValueError):
                pass
    if "units" in stored and stored["units"]:
        out["units"] = stored["units"]
    return out


def save_settings(conn, values: dict):
    """Upsert only the provided keys. Values stored as TEXT."""
    for k, v in values.items():
        if k not in SETTINGS_DEFAULTS:
            continue  # ignore unknown keys
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (k, str(v)))
    conn.commit()
    return get_settings(conn)


def count_swings_for_player(conn, player_id):
    row = conn.execute("SELECT COUNT(*) c FROM swing WHERE player_id=?",
                       (player_id,)).fetchone()
    return row["c"]


def count_sessions_for_player(conn, player_id):
    row = conn.execute("SELECT COUNT(*) c FROM session WHERE player_id=?",
                       (player_id,)).fetchone()
    return row["c"]


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
    # Most-recent-first, with any open (live) session pinned to the top.
    # started_at is a normalized ISO-8601 UTC string, so a lexicographic DESC
    # sort is chronological; id DESC breaks same-timestamp ties deterministically.
    sql += " ORDER BY (ended_at IS NULL) DESC, started_at DESC, id DESC"
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


def list_swing_summaries(conn, player_id=None, session_id=None, limit=None):
    """Lightweight swing rows for a picker: id, created_at, club, has_shot,
    and two key impact metrics (hip_sway_in, shoulder_tilt_deg) when present.
    Newest first."""
    sql = "SELECT * FROM swing WHERE 1=1"
    args = []
    if player_id is not None:
        sql += " AND player_id=?"; args.append(player_id)
    if session_id is not None:
        sql += " AND session_id=?"; args.append(session_id)
    sql += " ORDER BY id DESC"
    if limit is not None:
        sql += " LIMIT ?"; args.append(limit)
    rows = conn.execute(sql, args).fetchall()
    out = []
    for r in rows:
        sw = _swing_from_row(r)
        metrics = {m.name: m.value for m in get_metrics(conn, sw.id)
                   if m.context == "impact"}
        out.append({
            "id": sw.id,
            "created_at": sw.created_at,
            "club": sw.club,
            "has_shot": sw.shot_id is not None,
            "hip_sway_in": metrics.get("hip_sway_in"),
            "shoulder_tilt_deg": metrics.get("shoulder_tilt_deg"),
        })
    return out


_SHOT_COLS = [
    "swing_id", "player_id", "session_id", "captured_at", "device_id",
    "shot_number", "ball_speed", "total_spin", "spin_axis", "hla", "vla",
    "carry", "club_speed", "attack_angle", "club_path", "face_to_target",
    "club", "raw_json", "dedupe_key",
]


def _dedupe_key(shot: Shot) -> str | None:
    """Deterministic content-derived SHA-1 key for duplicate detection.

    Returns a hex digest when raw_json is present (all real GSPro shots),
    or None for synthetic/seed shots that lack raw_json.  The partial UNIQUE
    index on shot(dedupe_key) only enforces uniqueness for non-NULL keys, so
    synthetic shots (None key) are always inserted fresh."""
    if not shot.raw_json:
        return None
    return hashlib.sha1(shot.raw_json.encode()).hexdigest()


def save_shot(conn, shot: Shot) -> Shot:
    """Insert shot, setting dedupe_key. Idempotent: if the same shot (same
    dedupe_key) is already in the DB, return the existing row unchanged."""
    shot.dedupe_key = _dedupe_key(shot)
    vals = [getattr(shot, c) for c in _SHOT_COLS]
    placeholders = ",".join("?" * len(_SHOT_COLS))
    try:
        cur = conn.execute(
            f"INSERT INTO shot({','.join(_SHOT_COLS)}) VALUES ({placeholders})", vals)
        conn.commit()
        shot.id = cur.lastrowid
        return shot
    except sqlite3.IntegrityError:
        # Unique index violation: shot already persisted (crash-replay scenario).
        # Fetch and return the existing row so callers get a valid id.
        conn.rollback()
        existing = conn.execute(
            "SELECT * FROM shot WHERE dedupe_key=?", (shot.dedupe_key,)).fetchone()
        if existing is not None:
            return _shot_from_row(existing)
        raise  # unexpected integrity error — re-raise


def link_shot_to_swing(conn, shot_id, swing_id):
    conn.execute("UPDATE shot SET swing_id=? WHERE id=?", (swing_id, shot_id))
    conn.execute("UPDATE swing SET shot_id=? WHERE id=?", (shot_id, swing_id))
    conn.commit()


def _landmarks_to_json(landmarks):
    return json.dumps([[lm.name, lm.x, lm.y, lm.z, lm.visibility]
                       for lm in landmarks])


def _landmarks_from_json(text):
    return [Landmark(n, x, y, z, v) for (n, x, y, z, v) in json.loads(text)]


def _landmarks3d_to_json(landmarks):
    return json.dumps([[lm.name, lm.x, lm.y, lm.z, lm.confidence]
                       for lm in landmarks])


def _landmarks3d_from_json(text):
    return [Landmark3D(n, x, y, z, c) for (n, x, y, z, c) in json.loads(text)]


def save_pose_3d_frames(conn, swing_id, frames_by_index):
    """frames_by_index: {frame_index: [Landmark3D]}."""
    rows = [(swing_id, idx, _landmarks3d_to_json(lms))
            for idx, lms in frames_by_index.items()]
    conn.executemany(
        "INSERT OR REPLACE INTO pose_3d_frame(swing_id, frame_index, "
        "landmarks_json) VALUES (?,?,?)", rows)
    conn.commit()
    return len(rows)


def get_pose_3d_frames(conn, swing_id):
    """Return {frame_index: [Landmark3D]} for the swing (empty dict if none)."""
    rows = conn.execute(
        "SELECT frame_index, landmarks_json FROM pose_3d_frame "
        "WHERE swing_id=? ORDER BY frame_index", (swing_id,)).fetchall()
    return {r["frame_index"]: _landmarks3d_from_json(r["landmarks_json"])
            for r in rows}


def clear_pose_3d_frames(conn, swing_id):
    cur = conn.execute("DELETE FROM pose_3d_frame WHERE swing_id=?", (swing_id,))
    conn.commit()
    return cur.rowcount


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


# Allowlisted ball/club history metrics -> safe SQL expression over the shot
# row. Keys match coach.ball_reference benchmark keys so the frontend can
# request one consistent set. "smash" and "launch" are derived.
SHOT_HISTORY_METRICS = {
    "ball_speed":   "ball_speed",
    "club_speed":   "club_speed",
    "spin":         "total_spin",
    "carry":        "carry",
    "launch":       "vla",
    "attack_angle": "attack_angle",
    "smash":        None,   # derived: ball_speed / club_speed
}


def shot_history(conn, player_id, metric, club=None):
    """Ball-metric trend for a player over time: list of
    (shot_id, captured_at, value) ordered by captured_at ascending.

    `metric` must be in SHOT_HISTORY_METRICS (validated against an allowlist;
    no arbitrary column is ever interpolated into SQL). Rows with a null value
    are excluded. If `club` is given, only shots with shot.club = club are
    returned. Raises ValueError for an unknown metric."""
    if metric not in SHOT_HISTORY_METRICS:
        raise ValueError(f"unknown shot metric: {metric!r}")

    args = [player_id]
    where_extra = ""
    if club is not None:
        where_extra = " AND club=?"
        args.append(club)

    if metric == "smash":
        sql = (
            "SELECT id, captured_at, ball_speed, club_speed FROM shot "
            "WHERE player_id=? AND ball_speed IS NOT NULL "
            "AND club_speed IS NOT NULL AND club_speed > 0"
            + where_extra + " ORDER BY captured_at")
        rows = conn.execute(sql, args).fetchall()
        return [(r["id"], r["captured_at"],
                 round(r["ball_speed"] / r["club_speed"], 2)) for r in rows]

    col = SHOT_HISTORY_METRICS[metric]
    sql = (
        f"SELECT id, captured_at, {col} AS value FROM shot "
        f"WHERE player_id=? AND {col} IS NOT NULL"
        + where_extra + " ORDER BY captured_at")
    rows = conn.execute(sql, args).fetchall()
    return [(r["id"], r["captured_at"], r["value"]) for r in rows]


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
                face_to_target=r["face_to_target"], club=r["club"],
                raw_json=r["raw_json"], dedupe_key=r["dedupe_key"])


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


def _row_to_calibration(r):
    return Calibration(id=r["id"], created_at=r["created_at"],
                       device_index=r["device_index"], cols=r["cols"],
                       rows=r["rows"], square_mm=r["square_mm"],
                       n_poses=r["n_poses"], reprojection_error=r["reprojection_error"],
                       calib_json=r["calib_json"], is_active=r["is_active"])


def save_calibration(conn, *, device_index, cols, rows, square_mm, n_poses,
                     reprojection_error, calib_json):
    """Insert a calibration and make it the active one (clears other actives)."""
    conn.execute("UPDATE calibration SET is_active=0")
    cur = conn.execute(
        "INSERT INTO calibration(created_at, device_index, cols, rows, square_mm,"
        " n_poses, reprojection_error, calib_json, is_active) "
        "VALUES (?,?,?,?,?,?,?,?,1)",
        (dbmod.now_iso(), device_index, cols, rows, square_mm, n_poses,
         reprojection_error, calib_json))
    conn.commit()
    return get_calibration(conn, cur.lastrowid)


def get_calibration(conn, cal_id):
    r = conn.execute("SELECT * FROM calibration WHERE id=?", (cal_id,)).fetchone()
    return _row_to_calibration(r) if r else None


def get_active_calibration(conn):
    r = conn.execute("SELECT * FROM calibration WHERE is_active=1 "
                     "ORDER BY id DESC LIMIT 1").fetchone()
    return _row_to_calibration(r) if r else None


def list_calibrations(conn):
    rows = conn.execute("SELECT * FROM calibration ORDER BY id DESC").fetchall()
    return [_row_to_calibration(r) for r in rows]


def set_active_calibration(conn, cal_id):
    """Atomically clear the active flag and set it on cal_id.

    Returns the Calibration on success, None if cal_id does not exist.
    The existing active calibration is NEVER cleared unless the target id
    actually exists (checked inside the same transaction)."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute("SELECT id FROM calibration WHERE id=?",
                           (cal_id,)).fetchone()
        if row is None:
            conn.execute("ROLLBACK")
            return None
        conn.execute("UPDATE calibration SET is_active=0")
        conn.execute("UPDATE calibration SET is_active=1 WHERE id=?", (cal_id,))
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return get_calibration(conn, cal_id)
