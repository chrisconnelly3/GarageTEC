# Data Store + Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the SQLite-backed `store/` package — the shared data types and repository API every other GarageTEC rock depends on.

**Architecture:** Python stdlib `sqlite3` (no ORM). One DB file; big media on disk with paths in the DB. A `store/` package exposing dataclasses (`models.py`) + a function-based repository (`repo.py`) over a `schema.sql`. Every repo function takes an open `sqlite3.Connection` as its first argument so tests can use `:memory:`.

**Tech Stack:** Python 3.12, stdlib `sqlite3`, `pytest` (dev only). No third-party runtime deps.

Spec: `docs/superpowers/specs/2026-06-03-batch0-data-store-design.md`

---

## File Structure

- `store/__init__.py` — package marker, re-exports models.
- `store/schema.sql` — table definitions (source of truth for schema).
- `store/db.py` — `connect()`, `init_db()`, `default_db_path()`, `SCHEMA_VERSION`, `now_iso()`.
- `store/models.py` — dataclasses: Player, Session, Swing, Shot, Landmark, PoseFrame, Moment, Metric, Media.
- `store/repo.py` — repository functions grouped by entity.
- `store/tests/test_db.py`, `test_players.py`, `test_sessions.py`, `test_swings.py`, `test_shots.py`, `test_pose.py`, `test_metrics.py`.
- `store/tests/conftest.py` — `db` fixture: a fresh in-memory initialized connection.
- `requirements-dev.txt` — `pytest`.

Convention: timestamps are ISO-8601 UTC strings via `db.now_iso()`. Repo functions return the dataclass with `id` populated.

---

## Task 1: Package scaffold + pytest

**Files:**
- Create: `store/__init__.py`
- Create: `requirements-dev.txt`
- Create: `store/tests/__init__.py`
- Create: `store/tests/conftest.py`

- [ ] **Step 1: Create package files**

`store/__init__.py`:
```python
"""GarageTEC data store: shared models + SQLite repository."""
```

`requirements-dev.txt`:
```
pytest>=8
```

`store/tests/__init__.py`: (empty file)

- [ ] **Step 2: Install pytest**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r requirements-dev.txt`
Expected: `Successfully installed pytest-...`

- [ ] **Step 3: Add the `db` fixture (will be wired up in Task 3)**

`store/tests/conftest.py`:
```python
import pytest
from store import db as dbmod


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()
```

- [ ] **Step 4: Commit**

```bash
git add store/ requirements-dev.txt
git commit -m "chore: scaffold store package + pytest"
```

---

## Task 2: schema.sql

**Files:**
- Create: `store/schema.sql`

- [ ] **Step 1: Write the schema** (mirrors the spec exactly)

`store/schema.sql`:
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

CREATE TABLE IF NOT EXISTS coaching (
  id INTEGER PRIMARY KEY,
  swing_id INTEGER REFERENCES swing(id),
  session_id INTEGER REFERENCES session(id),
  kind TEXT NOT NULL, content_json TEXT NOT NULL,
  model TEXT, created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_swing_session ON swing(session_id);
CREATE INDEX IF NOT EXISTS ix_swing_player ON swing(player_id);
CREATE INDEX IF NOT EXISTS ix_pose_swing ON pose_frame(swing_id, view);
CREATE INDEX IF NOT EXISTS ix_metric_swing ON metric(swing_id, name);
CREATE INDEX IF NOT EXISTS ix_shot_swing ON shot(swing_id);
CREATE INDEX IF NOT EXISTS ix_shot_session ON shot(session_id);
CREATE INDEX IF NOT EXISTS ix_session_player ON session(player_id, ended_at);
```

- [ ] **Step 2: Commit**

```bash
git add store/schema.sql
git commit -m "feat(store): add SQLite schema"
```

---

## Task 3: db.py — connect & init

**Files:**
- Create: `store/db.py`
- Test: `store/tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_db.py`:
```python
def test_init_creates_tables_and_version(db):
    names = {r["name"] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"player", "session", "swing", "shot", "pose_frame",
            "moment", "metric", "media", "schema_version"} <= names
    assert db.execute("SELECT version FROM schema_version").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest store/tests/test_db.py -v`
Expected: FAIL (import error: `store.db` has no `connect`).

- [ ] **Step 3: Write minimal implementation**

`store/db.py`:
```python
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def now_iso():
    return datetime.now(timezone.utc).isoformat()


def default_db_path():
    root = os.environ.get("GARAGETEC_DATA_DIR")
    base = Path(root) if root else Path(__file__).resolve().parents[1] / "data"
    base.mkdir(parents=True, exist_ok=True)
    return str(base / "garagetec.db")


def connect(path=None):
    conn = sqlite3.connect(path or default_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(path=None, conn=None):
    conn = conn or connect(path)
    conn.executescript((Path(__file__).parent / "schema.sql").read_text())
    if conn.execute("SELECT version FROM schema_version").fetchone() is None:
        conn.execute("INSERT INTO schema_version(version) VALUES (?)",
                     (SCHEMA_VERSION,))
    conn.commit()
    return conn
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest store/tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/db.py store/tests/test_db.py
git commit -m "feat(store): connect + init_db with WAL and schema versioning"
```

---

## Task 4: models.py — dataclasses

**Files:**
- Create: `store/models.py`
- Modify: `store/__init__.py` (re-export)
- Test: `store/tests/test_db.py` (append a construction test)

- [ ] **Step 1: Write the failing test** (append)

In `store/tests/test_db.py`:
```python
def test_models_construct():
    from store.models import Player, Shot, Landmark, PoseFrame
    p = Player(name="Chris", height_in=72.0, handedness="R")
    assert p.id is None and p.height_in == 72.0
    s = Shot(captured_at="t", ball_speed=148.2)
    assert s.swing_id is None and s.ball_speed == 148.2
    pf = PoseFrame(swing_id=1, view="face_on", frame_index=0, time_s=0.0,
                   landmarks=[Landmark("nose", 1.0, 2.0, 0.0, 0.9)])
    assert pf.landmarks[0].name == "nose"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_db.py::test_models_construct -v`
Expected: FAIL (`store.models` not found).

- [ ] **Step 3: Implement `store/models.py`**

```python
from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Player:
    name: str
    height_in: float
    handedness: str  # "R" or "L"
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Session:
    player_id: int
    started_at: str
    ended_at: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Swing:
    session_id: int
    player_id: int
    created_at: str
    source_video_path: Optional[str] = None
    view_layout: Optional[str] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    club: Optional[str] = None
    notes: Optional[str] = None
    shot_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Shot:
    captured_at: str
    swing_id: Optional[int] = None
    player_id: Optional[int] = None
    session_id: Optional[int] = None
    device_id: Optional[str] = None
    shot_number: Optional[int] = None
    ball_speed: Optional[float] = None
    total_spin: Optional[float] = None
    spin_axis: Optional[float] = None
    hla: Optional[float] = None
    vla: Optional[float] = None
    carry: Optional[float] = None
    club_speed: Optional[float] = None
    attack_angle: Optional[float] = None
    club_path: Optional[float] = None
    face_to_target: Optional[float] = None
    raw_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Landmark:
    name: str
    x: float
    y: float
    z: float
    visibility: float


@dataclass
class PoseFrame:
    swing_id: int
    view: str
    frame_index: int
    time_s: float
    landmarks: List[Landmark] = field(default_factory=list)
    source: str = "mediapipe_pose"
    id: Optional[int] = None


@dataclass
class Moment:
    swing_id: int
    kind: str
    view: Optional[str] = None
    frame_index: Optional[int] = None
    time_s: Optional[float] = None
    id: Optional[int] = None


@dataclass
class Metric:
    swing_id: int
    name: str
    context: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    method: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Media:
    swing_id: int
    kind: str
    path: str
    meta_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Coaching:
    swing_id: Optional[int]
    session_id: Optional[int]
    kind: str  # "swing" or "session"
    content_json: str
    model: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None
```

Append to `store/__init__.py`:
```python
from store.models import (  # noqa: F401
    Player, Session, Swing, Shot, Landmark, PoseFrame, Moment, Metric, Media,
    Coaching,
)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest store/tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/models.py store/__init__.py store/tests/test_db.py
git commit -m "feat(store): shared dataclasses"
```

---

## Task 5: repo — players

**Files:**
- Create: `store/repo.py`
- Test: `store/tests/test_players.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_players.py`:
```python
from store import repo
from store.models import Player


def test_create_and_list_player(db):
    p = repo.get_or_create_player(db, "Chris", 72.0, "R")
    assert p.id is not None and p.created_at is not None
    again = repo.get_or_create_player(db, "Chris", 72.0, "R")
    assert again.id == p.id  # same name => same row, not a duplicate
    repo.get_or_create_player(db, "Brother", 70.0, "R")
    names = sorted(pl.name for pl in repo.list_players(db))
    assert names == ["Brother", "Chris"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_players.py -v`
Expected: FAIL (`store.repo` import error).

- [ ] **Step 3: Implement (start `repo.py`)**

`store/repo.py`:
```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest store/tests/test_players.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_players.py
git commit -m "feat(store): player repo"
```

---

## Task 6: repo — sessions (incl. per-player open/idle logic)

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_sessions.py`

- [ ] **Step 1: Write the failing tests**

`store/tests/test_sessions.py`:
```python
from datetime import datetime, timezone, timedelta
from store import repo


def _player(db):
    return repo.get_or_create_player(db, "Chris", 72.0, "R").id


def test_open_session_and_resume(db):
    pid = _player(db)
    assert repo.get_open_session(db, pid) is None
    s = repo.create_session(db, pid)
    assert s.id is not None and s.ended_at is None
    assert repo.get_open_session(db, pid).id == s.id  # resumes the open one


def test_end_idle_sessions_closes_stale_only(db):
    pid = _player(db)
    s = repo.create_session(db, pid)
    # a shot 30 min ago => stale
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    repo.save_shot(db, _shot(pid, s.id, old))
    closed = repo.end_idle_sessions(db, idle_minutes=15)
    assert closed == 1
    assert repo.get_open_session(db, pid) is None


def test_end_idle_sessions_keeps_recent(db):
    pid = _player(db)
    s = repo.create_session(db, pid)
    from store.db import now_iso
    repo.save_shot(db, _shot(pid, s.id, now_iso()))
    assert repo.end_idle_sessions(db, idle_minutes=15) == 0
    assert repo.get_open_session(db, pid).id == s.id


def _shot(pid, sid, ts):
    from store.models import Shot
    return Shot(captured_at=ts, player_id=pid, session_id=sid, ball_speed=100.0)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_sessions.py -v`
Expected: FAIL (`create_session` not defined). (Note: `save_shot` arrives in Task 8; these tests will pass once both exist. Run the file after Task 8 to confirm green — or temporarily run only `test_open_session_and_resume` now.)

- [ ] **Step 3: Implement session functions** (append to `repo.py`)

```python
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
```

- [ ] **Step 4: Run to verify it passes** (after Task 8 lands `save_shot`)

Run: `python -m pytest store/tests/test_sessions.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_sessions.py
git commit -m "feat(store): session repo with per-player open/idle handling"
```

---

## Task 7: repo — swings

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_swings.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_swings.py`:
```python
from store import repo


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_add_get_list_swing(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "golf swing.MOV",
                        view_layout="side_by_side_LR", fps=29.98,
                        width=1920, height=1080, club="7i")
    assert sw.id is not None
    got = repo.get_swing(db, sw.id)
    assert got.source_video_path == "golf swing.MOV" and got.player_id == pid
    assert [s.id for s in repo.list_swings(db, session_id=sid)] == [sw.id]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_swings.py -v`
Expected: FAIL (`add_swing` not defined).

- [ ] **Step 3: Implement** (append to `repo.py`)

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest store/tests/test_swings.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_swings.py
git commit -m "feat(store): swing repo"
```

---

## Task 8: repo — shots + swing↔shot link

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_shots.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_shots.py`:
```python
import json
from store import repo
from store.models import Shot


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_save_shot_and_fields(db):
    pid, sid = _ctx(db)
    shot = Shot(captured_at="2026-06-03T00:00:00+00:00", player_id=pid,
                session_id=sid, ball_speed=148.2, total_spin=2710.0, vla=13.8,
                club_path=2.1, raw_json=json.dumps({"DeviceID": "R50"}))
    saved = repo.save_shot(db, shot)
    assert saved.id is not None and saved.ball_speed == 148.2


def test_link_shot_and_swing_both_directions(db):
    pid, sid = _ctx(db)
    shot = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid))
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    repo.link_shot_to_swing(db, shot.id, sw.id)
    assert repo.get_swing(db, sw.id).shot_id == shot.id
    row = db.execute("SELECT swing_id FROM shot WHERE id=?", (shot.id,)).fetchone()
    assert row["swing_id"] == sw.id
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_shots.py -v`
Expected: FAIL (`save_shot` not defined).

- [ ] **Step 3: Implement** (append to `repo.py`)

```python
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
```

- [ ] **Step 4: Run to verify it passes** (also re-run sessions tests now that `save_shot` exists)

Run: `python -m pytest store/tests/test_shots.py store/tests/test_sessions.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_shots.py
git commit -m "feat(store): shot repo + swing/shot linking"
```

---

## Task 9: repo — pose frames (landmark JSON round-trip)

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_pose.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_pose.py`:
```python
from store import repo
from store.models import Landmark, PoseFrame


def _swing(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return repo.add_swing(db, sid, pid, "v.MOV").id


def test_pose_frames_roundtrip(db):
    sw = _swing(db)
    frames = [
        PoseFrame(swing_id=sw, view="face_on", frame_index=i, time_s=i / 30.0,
                  landmarks=[Landmark("nose", 10.0 + i, 20.0, 0.1, 0.95),
                             Landmark("left_shoulder", 5.0, 15.0, 0.2, 0.9)])
        for i in range(3)
    ]
    n = repo.save_pose_frames(db, sw, "face_on", frames)
    assert n == 3
    loaded = repo.get_pose_frames(db, sw, "face_on")
    assert [f.frame_index for f in loaded] == [0, 1, 2]  # ordered
    assert loaded[1].landmarks[0].name == "nose"
    assert abs(loaded[1].landmarks[0].x - 11.0) < 1e-9
    assert loaded[0].source == "mediapipe_pose"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_pose.py -v`
Expected: FAIL (`save_pose_frames` not defined).

- [ ] **Step 3: Implement** (append to `repo.py`)

```python
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest store/tests/test_pose.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_pose.py
git commit -m "feat(store): pose frame repo with landmark JSON round-trip"
```

---

## Task 10: repo — moments, metrics, history, media

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_metrics.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_metrics.py`:
```python
from store import repo
from store.models import Moment, Metric, Media


def _swing(db, name="Chris"):
    pid = repo.get_or_create_player(db, name, 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, repo.add_swing(db, sid, pid, "v.MOV").id


def test_moments_and_metrics(db):
    _, sw = _swing(db)
    repo.save_moments(db, sw, [Moment(sw, "address", "face_on", 10, 0.33),
                               Moment(sw, "impact", "face_on", 120, 4.0)])
    kinds = {m.kind for m in repo.get_moments(db, sw)}
    assert kinds == {"address", "impact"}

    repo.save_metrics(db, sw, [
        Metric(sw, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
        Metric(sw, "hip_sway_in", "impact", 2.5, "in", "shoulder_ratio_0.24")])
    got = {(m.name, m.context): m.value for m in repo.get_metrics(db, sw)}
    assert got[("hip_sway_in", "impact")] == 2.5
    assert repo.clear_metrics(db, sw) == 2  # idempotent recompute support
    assert repo.get_metrics(db, sw) == []


def test_swing_history_orders_by_time(db):
    pid, sw1 = _swing(db, "Hist")
    sid = repo.get_open_session(db, pid).id
    sw2 = repo.add_swing(db, sid, pid, "v2.MOV").id
    repo.save_metrics(db, sw1, [Metric(sw1, "hip_sway_in", "impact", 2.0, "in", "m")])
    repo.save_metrics(db, sw2, [Metric(sw2, "hip_sway_in", "impact", 3.0, "in", "m")])
    hist = repo.swing_history(db, pid, "hip_sway_in", context="impact")
    assert [v for (_sid, _ts, v) in hist] == [2.0, 3.0]


def test_media(db):
    _, sw = _swing(db, "Media")
    repo.save_media(db, Media(sw, "annotated_video", "swings/x/annotated.mp4"))
    rows = repo.get_media(db, sw)
    assert rows[0].kind == "annotated_video"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_metrics.py -v`
Expected: FAIL (`save_moments` not defined).

- [ ] **Step 3: Implement** (append to `repo.py`)

```python
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
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest store/ -v`
Expected: PASS (all test files green).

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_metrics.py
git commit -m "feat(store): moments, metrics, history, media repo"
```

---

## Task 11: repo — sync helpers (unlink, unmatched) + coaching

**Files:**
- Modify: `store/repo.py`
- Test: `store/tests/test_sync_support.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_sync_support.py`:
```python
import json
from store import repo
from store.models import Shot, Coaching


def _ctx(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def test_unmatched_and_unlink(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    shot = repo.save_shot(db, Shot(captured_at="t", player_id=pid, session_id=sid))
    assert [s.id for s in repo.list_unmatched_swings(db, session_id=sid)] == [sw.id]
    assert [s.id for s in repo.list_unmatched_shots(db, player_id=pid)] == [shot.id]
    repo.link_shot_to_swing(db, shot.id, sw.id)
    assert repo.list_unmatched_swings(db, session_id=sid) == []
    assert repo.list_unmatched_shots(db, session_id=sid) == []
    repo.unlink_shot(db, sw.id)
    assert [s.id for s in repo.list_unmatched_swings(db, session_id=sid)] == [sw.id]
    assert [s.id for s in repo.list_unmatched_shots(db, session_id=sid)] == [shot.id]


def test_coaching(db):
    pid, sid = _ctx(db)
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    repo.save_coaching(db, Coaching(swing_id=sw.id, session_id=None, kind="swing",
                                    content_json=json.dumps({"headline": "good"}),
                                    model="claude"))
    repo.save_coaching(db, Coaching(swing_id=None, session_id=sid, kind="session",
                                    content_json=json.dumps({"headline": "nice session"})))
    swing_c = repo.get_coaching(db, swing_id=sw.id)
    assert len(swing_c) == 1 and swing_c[0].kind == "swing"
    sess_c = repo.get_coaching(db, session_id=sid)
    assert len(sess_c) == 1 and sess_c[0].kind == "session"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest store/tests/test_sync_support.py -v`
Expected: FAIL (`list_unmatched_swings` not defined).

- [ ] **Step 3: Implement** (append to `repo.py`; also add `Coaching` to the
  `from store.models import (...)` line at the top of `repo.py`)

```python
def _shot_from_row(r):
    return Shot(id=r["id"], swing_id=r["swing_id"], player_id=r["player_id"],
                session_id=r["session_id"], captured_at=r["captured_at"],
                device_id=r["device_id"], shot_number=r["shot_number"],
                ball_speed=r["ball_speed"], total_spin=r["total_spin"],
                spin_axis=r["spin_axis"], hla=r["hla"], vla=r["vla"],
                carry=r["carry"], club_speed=r["club_speed"],
                attack_angle=r["attack_angle"], club_path=r["club_path"],
                face_to_target=r["face_to_target"], raw_json=r["raw_json"])


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
```

- [ ] **Step 4: Run the full suite**

Run: `python -m pytest store/ -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add store/repo.py store/tests/test_sync_support.py
git commit -m "feat(store): unmatched queries, unlink, and coaching repo"
```

---

## Done criteria

- `python -m pytest store/ -v` is fully green.
- `store/` exposes models + repo covering every table in the spec.
- No third-party runtime dependency; `data/` is created on demand and gitignored.
