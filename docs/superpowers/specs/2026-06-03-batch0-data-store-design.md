# Batch 0 — Data Store + Contracts

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Foundation rock. Built first. Every other rock depends on it.

---

## 1. Purpose

Provide the single, stable place all swing data lives, plus the shared Python
types and repository functions that every other rock uses instead of touching
SQL directly. This is the "contracts" layer — freezing it early is what lets
R50 ingest, vision, metrics, sync, AI coach, and the UI be built (and delegated)
without fighting over interfaces.

## 2. Scope

**In scope**
- SQLite database (one file) via Python stdlib `sqlite3` (no ORM, no deps).
- Schema for: player, session, swing, shot, pose_frame, moment, metric, media.
- Shared dataclasses (the typed contract) and a thin repository API.
- Schema versioning hook for future migrations.
- File-on-disk media storage with DB-stored paths.

**Out of scope**
- Postgres / networked DB, authentication, multi-user concerns.
- Heavy analytics / reporting (only basic history query for trends).
- An ORM. Any HTTP/service layer (rocks import the package directly).

## 3. Engine & Layout

- DB: `data/garagetec.db` (path configurable; default under a `data/` root).
- Media: large files (videos, keyframe images) live on disk under
  `data/media/<swing_id>/`; the DB stores **relative paths**, never blobs.
- `data/` root is gitignored (user content). Default root resolves relative to
  the repo unless overridden by `GARAGETEC_DATA_DIR`.

## 4. Package Structure (`store/`)

```
store/
  __init__.py
  db.py        # connect(), init_db(), schema_version, applies schema.sql
  schema.sql   # table definitions
  models.py    # shared dataclasses (THE typed contract)
  repo.py      # functions every rock calls
  tests/
    test_repo.py
```

## 5. Shared Types (`store/models.py`) — the typed contract

Dataclasses (fields abbreviated; all get an `id` once persisted):

- `Player(name, height_in, handedness)` — handedness in {"R","L"}.
- `Session(player_id, started_at, ended_at, location, notes)`
- `Swing(session_id, created_at, source_video_path, view_layout, fps, width,
  height, club, notes, shot_id|None)` — `view_layout` e.g. "side_by_side_LR".
- `Shot(swing_id|None, captured_at, device_id, shot_number, ball_speed,
  total_spin, spin_axis, hla, vla, carry, club_speed, attack_angle, club_path,
  face_to_target, raw_json)` — known fields as columns + `raw_json` for the rest.
- `Landmark(name, x, y, z, visibility)` — x,y in pixels of the cropped view;
  z = MediaPipe relative depth; visibility 0..1.
- `PoseFrame(swing_id, view, frame_index, time_s, landmarks: list[Landmark],
  source)` — `view` in {"face_on","down_line"}; `source` e.g. "mediapipe_pose".
- `Moment(swing_id, kind, view, frame_index, time_s)` — `kind` in
  {"address","top","impact","takeaway","lead_arm_parallel","transition",
  "shaft_parallel","follow_through"} (slice 1 uses first three).
- `Metric(swing_id, name, context, value, unit, method)` — `context` in
  {"address","top","impact","overall",...}; `method` documents how computed
  (e.g. "shoulder_ratio_0.24").
- `Media(swing_id, kind, path, meta_json)` — `kind` in
  {"source_video","annotated_video","keyframe"}.

## 6. Schema (`store/schema.sql`)

```sql
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
  created_at TEXT NOT NULL,
  source_video_path TEXT,
  view_layout TEXT, fps REAL, width INTEGER, height INTEGER,
  club TEXT, notes TEXT,
  shot_id INTEGER REFERENCES shot(id)
);

CREATE TABLE IF NOT EXISTS shot (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER REFERENCES swing(id),
  captured_at TEXT, device_id TEXT, shot_number INTEGER,
  ball_speed REAL, total_spin REAL, spin_axis REAL, hla REAL, vla REAL,
  carry REAL, club_speed REAL, attack_angle REAL, club_path REAL,
  face_to_target REAL,
  raw_json TEXT
);

CREATE TABLE IF NOT EXISTS pose_frame (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER NOT NULL REFERENCES swing(id),
  view TEXT NOT NULL, frame_index INTEGER NOT NULL, time_s REAL,
  landmarks_json TEXT NOT NULL, source TEXT,
  UNIQUE(swing_id, view, frame_index)
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

CREATE INDEX IF NOT EXISTS ix_swing_session ON swing(session_id);
CREATE INDEX IF NOT EXISTS ix_pose_swing ON pose_frame(swing_id, view);
CREATE INDEX IF NOT EXISTS ix_metric_swing ON metric(swing_id, name);
CREATE INDEX IF NOT EXISTS ix_shot_swing ON shot(swing_id);
```

Note: `swing.shot_id` and `shot.swing_id` intentionally both exist — a swing
may be created before its shot is matched (vision-first) or a shot before its
swing (R50-first). The **Sync** rock resolves the link; either side may be null
until then.

## 7. Repository API (`store/repo.py`) — contract surface

Signatures (illustrative; return persisted dataclasses or ids):

- `init_db(path=None) -> Connection`
- `get_or_create_player(name, height_in, handedness) -> Player`
- `create_session(player_id, location=None, notes=None) -> Session`
- `end_session(session_id) -> None`
- `add_swing(session_id, source_video_path, *, view_layout, fps, width, height,
  club=None, notes=None) -> Swing`
- `save_pose_frames(swing_id, view, frames: list[PoseFrame]) -> int`
- `save_moments(swing_id, moments: list[Moment]) -> int`
- `save_metrics(swing_id, metrics: list[Metric]) -> int`
- `save_shot(shot: Shot) -> Shot`
- `link_shot_to_swing(shot_id, swing_id) -> None`
- `get_swing(swing_id) -> Swing | None`
- `list_swings(session_id=None, limit=None) -> list[Swing]`
- `get_pose_frames(swing_id, view) -> list[PoseFrame]`
- `get_moments(swing_id) -> list[Moment]`
- `get_metrics(swing_id) -> list[Metric]`
- `swing_history(player_id, metric_name, context="overall") -> list[(swing_id,
  created_at, value)]`  # powers trend tracking

Connections use row factory for dict-like access; timestamps stored as ISO‑8601
text (UTC). Writes wrapped in transactions; `save_pose_frames` batch-inserts.

## 8. Migrations

`init_db` creates tables if absent and stamps `schema_version` (start at 1).
Future schema changes bump the version and run ordered migration steps. No
migration framework now — a simple version integer + if-ladder is enough.

## 9. Testing

- In-memory SQLite (`:memory:`) for fast unit tests.
- Round-trip every entity through repo create→get.
- **Pose fidelity:** save N `PoseFrame`s with 33 landmarks, reload, assert
  values match (incl. float tolerance) and ordering by frame_index.
- **Metric flexibility:** insert several metric names/contexts, query back.
- **Link logic:** create swing without shot, create shot, link, verify both
  directions resolve.
- **History query:** seed swings across time, assert `swing_history` returns
  ordered (time, value) pairs.

## 10. Risks

- SQLite single-writer: fine for single-user; if R50 ingest and vision write
  concurrently, use a short-lived connection per write + WAL mode to avoid
  "database is locked". Enable WAL in `init_db`.
- Landmarks as JSON text is simple but not query-optimized — acceptable; we
  query by swing/view, not by landmark value.
- Schema churn as later rocks appear — mitigated by the flexible `metric` table
  and `raw_json` on shot; bump schema_version when structural changes are needed.

## 11. Consumed By

- **R50 ingest** → `save_shot`, `create_session`.
- **Camera+pose+chop** → `add_swing`, `save_pose_frames`, `save_moments`, media.
- **Metrics brain** → `get_pose_frames`/`get_moments` → `save_metrics`.
- **Sync** → `link_shot_to_swing`.
- **AI coach** → `get_metrics`, `get_swing`, shot data.
- **Screen/UI** → `list_swings`, `get_*`, `swing_history`.
