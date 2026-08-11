CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS player (
  id INTEGER PRIMARY KEY,
  name TEXT, height_in REAL, handedness TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY,
  player_id INTEGER REFERENCES player(id),
  started_at TEXT NOT NULL, ended_at TEXT,
  location TEXT, notes TEXT
);

CREATE TABLE IF NOT EXISTS swing (
  id INTEGER PRIMARY KEY,
  session_id INTEGER REFERENCES session(id),
  player_id INTEGER REFERENCES player(id),
  created_at TEXT NOT NULL,
  source_video_path TEXT,
  view_layout TEXT, fps REAL, width INTEGER, height INTEGER,
  club TEXT, notes TEXT,
  shot_id INTEGER REFERENCES shot(id)
);

CREATE TABLE IF NOT EXISTS shot (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER REFERENCES swing(id),
  player_id INTEGER REFERENCES player(id),
  session_id INTEGER REFERENCES session(id),
  captured_at TEXT, device_id TEXT, shot_number INTEGER,
  ball_speed REAL, total_spin REAL, spin_axis REAL, hla REAL, vla REAL,
  carry REAL, club_speed REAL, attack_angle REAL, club_path REAL,
  face_to_target REAL,
  club TEXT,
  raw_json TEXT,
  dedupe_key TEXT,
  enrichment_json TEXT
);

CREATE TABLE IF NOT EXISTS pose_frame (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  view TEXT NOT NULL, frame_index INTEGER NOT NULL, time_s REAL,
  landmarks_json TEXT NOT NULL, source TEXT,
  UNIQUE(swing_id, view, frame_index)
);

CREATE TABLE IF NOT EXISTS pose_3d_frame (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  frame_index INTEGER NOT NULL,
  landmarks_json TEXT NOT NULL,
  UNIQUE(swing_id, frame_index)
);

CREATE TABLE IF NOT EXISTS calibration (
  id INTEGER PRIMARY KEY,
  created_at TEXT NOT NULL,
  device_index INTEGER NOT NULL,
  cols INTEGER NOT NULL, rows INTEGER NOT NULL, square_mm REAL NOT NULL,
  n_poses INTEGER NOT NULL, reprojection_error REAL NOT NULL,
  calib_json TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS moment (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  kind TEXT NOT NULL, view TEXT, frame_index INTEGER, time_s REAL
);

CREATE TABLE IF NOT EXISTS metric (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  name TEXT NOT NULL, context TEXT, value REAL, unit TEXT, method TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS media (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  kind TEXT NOT NULL, path TEXT NOT NULL, meta_json TEXT
);

CREATE TABLE IF NOT EXISTS coaching (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER REFERENCES swing(id),
  session_id INTEGER REFERENCES session(id),
  kind TEXT NOT NULL, content_json TEXT NOT NULL,
  model TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);

CREATE INDEX IF NOT EXISTS ix_swing_session ON swing(session_id);
CREATE INDEX IF NOT EXISTS ix_swing_player ON swing(player_id);
CREATE INDEX IF NOT EXISTS ix_pose_swing ON pose_frame(swing_id, view);
CREATE INDEX IF NOT EXISTS ix_metric_swing ON metric(swing_id, name);
CREATE INDEX IF NOT EXISTS ix_shot_swing ON shot(swing_id);
CREATE INDEX IF NOT EXISTS ix_shot_session ON shot(session_id);
CREATE INDEX IF NOT EXISTS ix_session_player ON session(player_id, ended_at);
