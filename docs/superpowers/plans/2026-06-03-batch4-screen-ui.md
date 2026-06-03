# Screen / UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build GarageTEC's local web app — a FastAPI backend (REST + SSE + media serving over the Batch 0 store and Sync rock) and a minimal React/Vite frontend (six screens) prebuilt to static files the backend serves single-origin.

**Architecture:** A `web/backend/` FastAPI app exposes thin read endpoints over `store.repo` and write endpoints wrapping the Sync rock, plus an SSE `/events` stream backed by a store-polling watcher that detects newly-ready swings, and a path-safe `/media/{path}` server rooted at `data/media`. A request-scoped store connection is provided through a `deps.py` dependency so tests inject an in-memory store via FastAPI's dependency override. A `web/frontend/` React (Vite) app renders the six screens through a shared API client and an SSE hook; it is built to static assets that FastAPI mounts (no CORS).

**Tech Stack:** Python 3.12, FastAPI, uvicorn, httpx (TestClient), pytest, stdlib `sqlite3` (existing `store/`); React 18 + Vite 5, Recharts, vitest + @testing-library/react.

Spec: `docs/superpowers/specs/2026-06-03-batch4-screen-ui-design.md`
Depends on: `store/repo.py`, `store/models.py`, `store/db.py`, `sync/service.py` (`SyncService`).

Python (full path; `py` launcher NOT on PATH): `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`
Node/npm: `C:\Program Files\nodejs` (on PATH as `npm`).

---

## File Structure

### Backend — `web/backend/`

- `web/__init__.py` — package marker (empty).
- `web/backend/__init__.py` — package marker (empty).
- `web/backend/requirements.txt` — `fastapi`, `uvicorn`, `httpx` (TestClient transport).
- `web/backend/deps.py` — `get_conn()` request-scoped store connection dependency + `media_root()`; overridable in tests.
- `web/backend/app.py` — builds the FastAPI app (`create_app()`), includes the routers, mounts media + SSE, mounts the built static frontend last.
- `web/backend/api_players.py` — `GET /api/players`, `POST /api/players`.
- `web/backend/api_sessions.py` — `GET /api/sessions`, `GET /api/sessions/{id}`.
- `web/backend/api_swings.py` — `GET /api/swings/{id}` (aggregates metrics + moments + shot + coaching + media).
- `web/backend/api_history.py` — `GET /api/history?player=&metric=&context=`.
- `web/backend/api_sync.py` — `GET /api/sync/proposals?session=`, `POST /api/sync/apply`, `POST /api/sync/unlink`.
- `web/backend/events.py` — `SwingWatcher` (store-polling, detects newly-ready swings) + `GET /events` SSE route.
- `web/backend/media.py` — `GET /media/{path}` path-traversal-safe file serving from `data/media`.
- `web/backend/serializers.py` — pure dict builders (dataclass → JSON-safe dict) shared by the routers.
- `web/backend/tests/__init__.py` — package marker (empty).
- `web/backend/tests/conftest.py` — in-memory store fixture + `client` fixture (TestClient with `get_conn`/`media_root` overridden); shared seed helpers.
- `web/backend/tests/test_api_players.py`
- `web/backend/tests/test_api_sessions.py`
- `web/backend/tests/test_api_swings.py`
- `web/backend/tests/test_api_history.py`
- `web/backend/tests/test_api_sync.py`
- `web/backend/tests/test_events.py` — watcher tested by seeding the store (no wall-clock sleeps).
- `web/backend/tests/test_media.py` — serves a real file; rejects `..` traversal.

### Frontend — `web/frontend/`

- `web/frontend/package.json` — Vite/React deps + `dev`/`build`/`preview`/`test` scripts.
- `web/frontend/vite.config.js` — React plugin, `base: "./"`, build `outDir: "dist"`, dev proxy of `/api`,`/events`,`/media` → `http://localhost:8000`, vitest config (jsdom).
- `web/frontend/index.html` — Vite entry.
- `web/frontend/src/main.jsx` — React root + router.
- `web/frontend/src/App.jsx` — layout + nav across the six pages.
- `web/frontend/src/api.js` — shared fetch client (`getPlayers`, `createPlayer`, `getSessions`, `getSession`, `getSwing`, `getHistory`, `getProposals`, `applyMatch`, `unlinkSwing`).
- `web/frontend/src/useEvents.js` — SSE hook: subscribes to `/events`, returns the latest `swing_ready` payload.
- `web/frontend/src/components/MetricCard.jsx` — value + vs-baseline + vs-ideal + confidence flag.
- `web/frontend/src/components/MetricCard.test.jsx` — vitest component test.
- `web/frontend/src/pages/Live.jsx` — live / last-swing.
- `web/frontend/src/pages/SwingReview.jsx` — clip + moments timeline + metric table + AI feedback + matched shot.
- `web/frontend/src/pages/Session.jsx` — session swings + summary + in-session trend.
- `web/frontend/src/pages/History.jsx` — per-metric line chart over time, filter by player + context.
- `web/frontend/src/pages/SyncFix.jsx` — unmatched + proposals; apply / unlink.
- `web/frontend/src/pages/Players.jsx` — roster management (name, height, handedness).

Conventions: every repo call passes `conn` first (Batch 0 contract). All timestamps are ISO-8601 UTC strings from `store.db.now_iso()`. Routers return plain dicts/lists (FastAPI JSON-encodes). The frontend talks only to same-origin `/api`, `/events`, `/media`.

---

## Task 1: Store additions — `list_sessions` + `get_session`

The Screen needs to list sessions (optionally per player) and fetch one by id; neither exists in `store/repo.py` today. Add them with tests, mirroring how earlier rocks added `get_player`/`get_swing`.

**Files:**
- Modify: `store/repo.py`
- Create: `store/tests/test_sessions_query.py`

- [ ] **Step 1: Write the failing test**

`store/tests/test_sessions_query.py`:
```python
from store import repo


def _player(db, name="Chris"):
    return repo.get_or_create_player(db, name, 72.0, "R").id


def test_get_session_returns_row_or_none(db):
    assert repo.get_session(db, 999) is None
    pid = _player(db)
    s = repo.create_session(db, pid, location="bay")
    got = repo.get_session(db, s.id)
    assert got is not None
    assert got.id == s.id and got.player_id == pid and got.location == "bay"


def test_list_sessions_all_and_by_player_newest_first(db):
    a = _player(db, "A")
    b = _player(db, "B")
    s_a1 = repo.create_session(db, a)
    s_b1 = repo.create_session(db, b)
    s_a2 = repo.create_session(db, a)
    all_ids = [s.id for s in repo.list_sessions(db)]
    assert all_ids == [s_a2.id, s_b1.id, s_a1.id]  # newest id first
    a_ids = [s.id for s in repo.list_sessions(db, player_id=a)]
    assert a_ids == [s_a2.id, s_a1.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/tests/test_sessions_query.py -v`
Expected: FAIL (`module 'store.repo' has no attribute 'get_session'`).

- [ ] **Step 3: Write minimal implementation** (append to `store/repo.py`, after `get_open_session`)

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/tests/test_sessions_query.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full store suite (no regressions)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add store/repo.py store/tests/test_sessions_query.py
git commit -m "feat(store): list_sessions + get_session for the Screen"
```

---

## Task 2: Backend scaffold + dependencies

**Files:**
- Create: `web/__init__.py` (empty)
- Create: `web/backend/__init__.py` (empty)
- Create: `web/backend/requirements.txt`
- Create: `web/backend/deps.py`
- Create: `web/backend/tests/__init__.py` (empty)
- Create: `web/backend/tests/conftest.py`
- Create: `web/backend/app.py`
- Create: `web/backend/tests/test_app_health.py`

- [ ] **Step 1: Create package + requirements files**

`web/__init__.py`: (empty file)
`web/backend/__init__.py`: (empty file)
`web/backend/tests/__init__.py`: (empty file)

`web/backend/requirements.txt`:
```
fastapi>=0.111
uvicorn>=0.30
httpx>=0.27
```

- [ ] **Step 2: Install backend deps**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install -r web/backend/requirements.txt`
Expected: `Successfully installed fastapi-... uvicorn-... httpx-... starlette-...` (pytest already present from Batch 0's `requirements-dev.txt`).

- [ ] **Step 3: Write `deps.py`** (the connection + media-root seams tests override)

`web/backend/deps.py`:
```python
"""Request-scoped dependencies for the Screen backend.

`get_conn` yields a store connection per request; tests override it with an
in-memory connection. `media_root` returns the directory media is served from;
tests override it with a temp dir.
"""
from pathlib import Path

from store import db as dbmod


def get_conn():
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    try:
        yield conn
    finally:
        conn.close()


def media_root() -> Path:
    return Path(dbmod.default_db_path()).parent / "media"
```

- [ ] **Step 4: Write the failing health test**

`web/backend/tests/test_app_health.py`:
```python
def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 5: Write `conftest.py`** (in-memory store + TestClient with overrides)

`web/backend/tests/conftest.py`:
```python
import json

import pytest
from fastapi.testclient import TestClient

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Media, Coaching
from web.backend.app import create_app
from web.backend import deps


@pytest.fixture
def conn():
    c = dbmod.connect(":memory:")
    dbmod.init_db(conn=c)
    yield c
    c.close()


@pytest.fixture
def client(conn, tmp_path):
    app = create_app()
    app.dependency_overrides[deps.get_conn] = lambda: conn
    media_dir = tmp_path / "media"
    media_dir.mkdir()
    app.dependency_overrides[deps.media_root] = lambda: media_dir
    with TestClient(app) as c:
        c.media_dir = media_dir  # expose for media tests
        yield c


# ---- shared seed helpers ------------------------------------------------

def seed_player(conn, name="Chris", height_in=72.0, handedness="R"):
    return repo.get_or_create_player(conn, name, height_in, handedness)


def seed_ready_swing(conn, player, *, club="7i"):
    """A fully processed swing: metrics + moments + media + coaching + a
    linked shot. Returns the swing."""
    sid = repo.create_session(conn, player.id, location="bay").id
    swing = repo.add_swing(conn, sid, player.id, "swings/1/source.mp4",
                           view_layout="face_on", fps=240.0, width=1920,
                           height=1080, club=club)
    shot = repo.save_shot(conn, Shot(captured_at=dbmod.now_iso(),
                                     player_id=player.id, session_id=sid,
                                     ball_speed=148.2, carry=172.0, vla=13.8))
    repo.link_shot_to_swing(conn, shot.id, swing.id)
    repo.save_moments(conn, swing.id, [
        Moment(swing.id, "address", "face_on", 0, 0.0),
        Moment(swing.id, "impact", "face_on", 120, 0.5),
    ])
    repo.save_metrics(conn, swing.id, [
        Metric(swing.id, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
        Metric(swing.id, "hip_sway_in", "impact", 2.5, "in", "ratio"),
    ])
    repo.save_media(conn, Media(swing.id, "annotated_video",
                                "swings/1/annotated.mp4"))
    repo.save_coaching(conn, Coaching(
        swing_id=swing.id, session_id=None, kind="swing",
        content_json=json.dumps({"headline": "Solid contact",
                                 "findings": ["good tilt"],
                                 "drills": ["towel drill"]}),
        model="claude"))
    return swing
```

- [ ] **Step 6: Write minimal `app.py`**

`web/backend/app.py`:
```python
"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    return app
```

- [ ] **Step 7: Run the test to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_app_health.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add web/__init__.py web/backend/ store/
git commit -m "feat(web): FastAPI scaffold, deps, test fixtures"
```

---

## Task 3: Serializers (dataclass → JSON dict)

Pure functions so the routers stay thin and the shapes are tested once.

**Files:**
- Create: `web/backend/serializers.py`
- Create: `web/backend/tests/test_serializers.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_serializers.py`:
```python
import json

from store.models import Player, Session, Swing, Shot, Moment, Metric, Media, Coaching
from web.backend import serializers as ser


def test_player_dict():
    p = Player(id=3, name="Chris", height_in=72.0, handedness="R",
               created_at="2026-06-03T00:00:00+00:00")
    assert ser.player_dict(p) == {
        "id": 3, "name": "Chris", "height_in": 72.0, "handedness": "R",
        "created_at": "2026-06-03T00:00:00+00:00"}


def test_session_dict():
    s = Session(id=1, player_id=3, started_at="t", ended_at=None,
                location="bay", notes=None)
    d = ser.session_dict(s)
    assert d["id"] == 1 and d["player_id"] == 3 and d["location"] == "bay"


def test_metric_and_moment_dicts():
    m = Metric(5, "hip_sway_in", "impact", 2.5, "in", "ratio", "t", id=9)
    assert ser.metric_dict(m) == {
        "id": 9, "swing_id": 5, "name": "hip_sway_in", "context": "impact",
        "value": 2.5, "unit": "in", "method": "ratio", "created_at": "t"}
    mo = Moment(5, "impact", "face_on", 120, 0.5, id=2)
    assert ser.moment_dict(mo)["kind"] == "impact"


def test_coaching_dict_parses_content_json():
    c = Coaching(swing_id=5, session_id=None, kind="swing",
                 content_json=json.dumps({"headline": "hi"}), model="claude",
                 created_at="t", id=1)
    d = ser.coaching_dict(c)
    assert d["content"] == {"headline": "hi"}  # parsed, not a raw string


def test_shot_and_media_dicts():
    sh = Shot(captured_at="t", id=7, ball_speed=148.2, carry=172.0)
    assert ser.shot_dict(sh)["ball_speed"] == 148.2
    md = Media(swing_id=5, kind="annotated_video", path="swings/1/a.mp4", id=4)
    assert ser.media_dict(md) == {"id": 4, "swing_id": 5,
                                  "kind": "annotated_video",
                                  "path": "swings/1/a.mp4", "meta": None}
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_serializers.py -v`
Expected: FAIL (`No module named 'web.backend.serializers'`).

- [ ] **Step 3: Implement `serializers.py`**

`web/backend/serializers.py`:
```python
"""Pure dataclass -> JSON-safe dict builders for the Screen API."""
import json


def player_dict(p):
    return {"id": p.id, "name": p.name, "height_in": p.height_in,
            "handedness": p.handedness, "created_at": p.created_at}


def session_dict(s):
    return {"id": s.id, "player_id": s.player_id, "started_at": s.started_at,
            "ended_at": s.ended_at, "location": s.location, "notes": s.notes}


def swing_dict(sw):
    return {"id": sw.id, "session_id": sw.session_id, "player_id": sw.player_id,
            "created_at": sw.created_at, "source_video_path": sw.source_video_path,
            "view_layout": sw.view_layout, "fps": sw.fps, "width": sw.width,
            "height": sw.height, "club": sw.club, "notes": sw.notes,
            "shot_id": sw.shot_id}


def shot_dict(sh):
    if sh is None:
        return None
    return {"id": sh.id, "swing_id": sh.swing_id, "player_id": sh.player_id,
            "session_id": sh.session_id, "captured_at": sh.captured_at,
            "device_id": sh.device_id, "shot_number": sh.shot_number,
            "ball_speed": sh.ball_speed, "total_spin": sh.total_spin,
            "spin_axis": sh.spin_axis, "hla": sh.hla, "vla": sh.vla,
            "carry": sh.carry, "club_speed": sh.club_speed,
            "attack_angle": sh.attack_angle, "club_path": sh.club_path,
            "face_to_target": sh.face_to_target}


def moment_dict(m):
    return {"id": m.id, "swing_id": m.swing_id, "kind": m.kind, "view": m.view,
            "frame_index": m.frame_index, "time_s": m.time_s}


def metric_dict(m):
    return {"id": m.id, "swing_id": m.swing_id, "name": m.name,
            "context": m.context, "value": m.value, "unit": m.unit,
            "method": m.method, "created_at": m.created_at}


def media_dict(md):
    meta = json.loads(md.meta_json) if md.meta_json else None
    return {"id": md.id, "swing_id": md.swing_id, "kind": md.kind,
            "path": md.path, "meta": meta}


def coaching_dict(c):
    content = json.loads(c.content_json) if c.content_json else None
    return {"id": c.id, "swing_id": c.swing_id, "session_id": c.session_id,
            "kind": c.kind, "content": content, "model": c.model,
            "created_at": c.created_at}
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_serializers.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/backend/serializers.py web/backend/tests/test_serializers.py
git commit -m "feat(web): JSON serializers for store dataclasses"
```

---

## Task 4: Players API

**Files:**
- Create: `web/backend/api_players.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_api_players.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_players.py`:
```python
from web.backend.tests.conftest import seed_player


def test_list_players_empty(client):
    assert client.get("/api/players").json() == []


def test_create_then_list_players(client):
    r = client.post("/api/players", json={"name": "Chris", "height_in": 72.0,
                                          "handedness": "R"})
    assert r.status_code == 200
    body = r.json()
    assert body["id"] is not None and body["name"] == "Chris"

    names = [p["name"] for p in client.get("/api/players").json()]
    assert names == ["Chris"]


def test_create_player_is_idempotent_by_name(client, conn):
    seed_player(conn, "Chris")
    r = client.post("/api/players", json={"name": "Chris", "height_in": 72.0,
                                          "handedness": "R"})
    assert r.status_code == 200
    assert len(client.get("/api/players").json()) == 1  # no duplicate row
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_players.py -v`
Expected: FAIL (404 — route not registered).

- [ ] **Step 3: Implement `api_players.py`**

`web/backend/api_players.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import player_dict

router = APIRouter(prefix="/api/players", tags=["players"])


class PlayerIn(BaseModel):
    name: str
    height_in: float
    handedness: str


@router.get("")
def list_players(conn=Depends(get_conn)):
    return [player_dict(p) for p in repo.list_players(conn)]


@router.post("")
def create_player(body: PlayerIn, conn=Depends(get_conn)):
    p = repo.get_or_create_player(conn, body.name, body.height_in,
                                  body.handedness)
    return player_dict(p)
```

- [ ] **Step 4: Wire the router into `app.py`**

In `web/backend/app.py`, replace the body of `create_app` so it imports and includes the router:
```python
"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from fastapi import FastAPI

from web.backend import api_players


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(api_players.router)
    return app
```

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_players.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api_players.py web/backend/app.py web/backend/tests/test_api_players.py
git commit -m "feat(web): players API"
```

---

## Task 5: Sessions API

`GET /api/sessions` (optional `?player=`) and `GET /api/sessions/{id}` (session + its swings, each with their shot for quick listing).

**Files:**
- Create: `web/backend/api_sessions.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_api_sessions.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_sessions.py`:
```python
from web.backend.tests.conftest import seed_player, seed_ready_swing


def test_list_sessions_filter_by_player(client, conn):
    a = seed_player(conn, "A")
    b = seed_player(conn, "B")
    seed_ready_swing(conn, a)
    seed_ready_swing(conn, b)

    all_sessions = client.get("/api/sessions").json()
    assert len(all_sessions) == 2

    a_only = client.get("/api/sessions", params={"player": a.id}).json()
    assert len(a_only) == 1 and a_only[0]["player_id"] == a.id


def test_get_session_includes_swings(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    sid = swing.session_id

    r = client.get(f"/api/sessions/{sid}")
    assert r.status_code == 200
    body = r.json()
    assert body["session"]["id"] == sid
    assert [s["id"] for s in body["swings"]] == [swing.id]
    assert body["swings"][0]["shot_id"] is not None
    assert body["coaching"] == []  # no session-level coaching seeded


def test_get_missing_session_404(client):
    assert client.get("/api/sessions/999").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_sessions.py -v`
Expected: FAIL (404 — routes not registered).

- [ ] **Step 3: Implement `api_sessions.py`**

`web/backend/api_sessions.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import session_dict, swing_dict, coaching_dict

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("")
def list_sessions(player: int | None = None, conn=Depends(get_conn)):
    return [session_dict(s) for s in repo.list_sessions(conn, player_id=player)]


@router.get("/{session_id}")
def get_session(session_id: int, conn=Depends(get_conn)):
    session = repo.get_session(conn, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found")
    swings = repo.list_swings(conn, session_id=session_id)
    coaching = repo.get_coaching(conn, session_id=session_id)
    return {
        "session": session_dict(session),
        "swings": [swing_dict(sw) for sw in swings],
        "coaching": [coaching_dict(c) for c in coaching],
    }
```

- [ ] **Step 4: Wire the router into `app.py`**

In `web/backend/app.py`, add the import `from web.backend import api_sessions` and `app.include_router(api_sessions.router)` after the players router.

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_sessions.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api_sessions.py web/backend/app.py web/backend/tests/test_api_sessions.py
git commit -m "feat(web): sessions API"
```

---

## Task 6: Swing detail API (the aggregate)

`GET /api/swings/{id}` returns the swing + metrics + moments + matched shot + coaching + media in one payload — the Live and Swing-review screens' core fetch.

**Files:**
- Create: `web/backend/api_swings.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_api_swings.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_swings.py`:
```python
from web.backend.tests.conftest import seed_player, seed_ready_swing


def test_swing_detail_aggregates_everything(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)

    r = client.get(f"/api/swings/{swing.id}")
    assert r.status_code == 200
    body = r.json()

    assert body["swing"]["id"] == swing.id and body["swing"]["club"] == "7i"
    names = {m["name"] for m in body["metrics"]}
    assert names == {"shoulder_tilt_deg", "hip_sway_in"}
    kinds = [m["kind"] for m in body["moments"]]
    assert kinds == ["address", "impact"]  # ordered by frame_index
    assert body["shot"]["ball_speed"] == 148.2
    assert body["coaching"][0]["content"]["headline"] == "Solid contact"
    assert body["media"][0]["kind"] == "annotated_video"


def test_swing_detail_unmatched_has_null_shot(client, conn):
    from store import repo
    p = seed_player(conn)
    sid = repo.create_session(conn, p.id).id
    swing = repo.add_swing(conn, sid, p.id, "v.mp4")

    body = client.get(f"/api/swings/{swing.id}").json()
    assert body["shot"] is None
    assert body["metrics"] == [] and body["coaching"] == []


def test_missing_swing_404(client):
    assert client.get("/api/swings/999").status_code == 404
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_swings.py -v`
Expected: FAIL (404 — route not registered).

- [ ] **Step 3: Implement `api_swings.py`**

`web/backend/api_swings.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import (
    swing_dict, metric_dict, moment_dict, shot_dict, coaching_dict, media_dict,
)

router = APIRouter(prefix="/api/swings", tags=["swings"])


@router.get("/{swing_id}")
def get_swing(swing_id: int, conn=Depends(get_conn)):
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise HTTPException(status_code=404, detail="swing not found")

    shot = None
    if swing.shot_id is not None:
        for sh in repo.list_unmatched_shots.__self__ if False else []:  # noqa
            pass
        row = conn.execute("SELECT * FROM shot WHERE id=?",
                           (swing.shot_id,)).fetchone()
        if row is not None:
            shot = repo._shot_from_row(row)

    return {
        "swing": swing_dict(swing),
        "metrics": [metric_dict(m) for m in repo.get_metrics(conn, swing_id)],
        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing_id)],
        "shot": shot_dict(shot),
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing_id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing_id)],
    }
```

> Note: `get_shot(conn, shot_id)` ALREADY EXISTS in `store/repo.py` (added by the
> AI coach rock, already on main) with its own test. Do NOT re-add it. Use
> `repo.get_shot(...)` directly, as in the clean `api_swings.py` below — discard
> the raw-SQL draft above.

Final `api_swings.py`:
```python
from fastapi import APIRouter, Depends, HTTPException

from store import repo
from web.backend.deps import get_conn
from web.backend.serializers import (
    swing_dict, metric_dict, moment_dict, shot_dict, coaching_dict, media_dict,
)

router = APIRouter(prefix="/api/swings", tags=["swings"])


@router.get("/{swing_id}")
def get_swing(swing_id: int, conn=Depends(get_conn)):
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise HTTPException(status_code=404, detail="swing not found")
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return {
        "swing": swing_dict(swing),
        "metrics": [metric_dict(m) for m in repo.get_metrics(conn, swing_id)],
        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing_id)],
        "shot": shot_dict(shot),
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing_id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing_id)],
    }
```

- [ ] **Step 4: (no store change needed)**

`get_shot` is already present in `store/repo.py` with its own test (added by the
AI coach rock). Skip this step — nothing to add to the store.

- [ ] **Step 5: Wire the router into `app.py`**

Add `from web.backend import api_swings` and `app.include_router(api_swings.router)`.

- [ ] **Step 6: Run to verify it passes** (store + web)

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/tests/test_shots.py web/backend/tests/test_api_swings.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/backend/api_swings.py web/backend/app.py web/backend/tests/test_api_swings.py
git commit -m "feat(web): swing detail aggregate API"
```

---

## Task 7: History API

`GET /api/history?player=&metric=&context=` — ordered points for a per-metric trend chart, via `repo.swing_history`.

**Files:**
- Create: `web/backend/api_history.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_api_history.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_history.py`:
```python
from store import repo
from store.models import Metric
from web.backend.tests.conftest import seed_player


def _swing(conn, pid):
    sid = repo.get_open_session(conn, pid)
    sid = sid.id if sid else repo.create_session(conn, pid).id
    return repo.add_swing(conn, sid, pid, "v.mp4").id


def test_history_returns_ordered_points(client, conn):
    p = seed_player(conn)
    s1 = _swing(conn, p.id)
    s2 = _swing(conn, p.id)
    repo.save_metrics(conn, s1, [Metric(s1, "hip_sway_in", "impact", 2.0, "in", "m")])
    repo.save_metrics(conn, s2, [Metric(s2, "hip_sway_in", "impact", 3.0, "in", "m")])

    r = client.get("/api/history", params={"player": p.id,
                                           "metric": "hip_sway_in",
                                           "context": "impact"})
    assert r.status_code == 200
    points = r.json()["points"]
    assert [pt["value"] for pt in points] == [2.0, 3.0]
    assert points[0]["swing_id"] == s1 and "created_at" in points[0]


def test_history_defaults_context_overall(client, conn):
    p = seed_player(conn)
    s1 = _swing(conn, p.id)
    repo.save_metrics(conn, s1, [Metric(s1, "tempo", "overall", 3.1, "ratio", "m")])
    r = client.get("/api/history", params={"player": p.id, "metric": "tempo"})
    assert [pt["value"] for pt in r.json()["points"]] == [3.1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_history.py -v`
Expected: FAIL (404 — route not registered).

- [ ] **Step 3: Implement `api_history.py`**

`web/backend/api_history.py`:
```python
from fastapi import APIRouter, Depends

from store import repo
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def history(player: int, metric: str, context: str = "overall",
            conn=Depends(get_conn)):
    rows = repo.swing_history(conn, player, metric, context=context)
    return {
        "player": player,
        "metric": metric,
        "context": context,
        "points": [{"swing_id": sid, "created_at": ts, "value": value}
                   for (sid, ts, value) in rows],
    }
```

- [ ] **Step 4: Wire the router into `app.py`**

Add `from web.backend import api_history` and `app.include_router(api_history.router)`.

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_history.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api_history.py web/backend/app.py web/backend/tests/test_api_history.py
git commit -m "feat(web): history API"
```

---

## Task 8: Sync API (proposals / apply / unlink)

Wraps `sync.service.SyncService`. Proposals are scoped per session; the service walks each (player, session) scope internally via `reconcile_session`-style logic, but for read-only proposals we enumerate the session's scopes and call `propose_matches` per scope.

**Files:**
- Create: `web/backend/api_sync.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_api_sync.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_api_sync.py`:
```python
from store import repo
from store.models import Shot
from store import db as dbmod
from web.backend.tests.conftest import seed_player


def _unmatched_pair(conn, player):
    sid = repo.create_session(conn, player.id).id
    swing = repo.add_swing(conn, sid, player.id, "v.mp4")
    shot = repo.save_shot(conn, Shot(captured_at=dbmod.now_iso(),
                                     player_id=player.id, session_id=sid))
    return sid, swing, shot


def test_proposals_lists_candidate_for_session(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    r = client.get("/api/sync/proposals", params={"session": sid})
    assert r.status_code == 200
    body = r.json()
    props = body["proposals"]
    assert any(pr["swing_id"] == swing.id and pr["shot_id"] == shot.id
               for pr in props)
    assert "confidence" in props[0] and "reason" in props[0]
    assert swing.id in [s["id"] for s in body["unmatched_swings"]]
    assert shot.id in [s["id"] for s in body["unmatched_shots"]]


def test_apply_links_swing_to_shot(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    r = client.post("/api/sync/apply",
                    json={"swing_id": swing.id, "shot_id": shot.id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert repo.get_swing(conn, swing.id).shot_id == shot.id


def test_unlink_clears_link(client, conn):
    p = seed_player(conn)
    sid, swing, shot = _unmatched_pair(conn, p)
    repo.link_shot_to_swing(conn, shot.id, swing.id)
    r = client.post("/api/sync/unlink", json={"swing_id": swing.id})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert repo.get_swing(conn, swing.id).shot_id is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_sync.py -v`
Expected: FAIL (404 — routes not registered).

- [ ] **Step 3: Implement `api_sync.py`**

`web/backend/api_sync.py`:
```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from store import repo
from sync.service import SyncService
from web.backend.deps import get_conn
from web.backend.serializers import swing_dict, shot_dict

router = APIRouter(prefix="/api/sync", tags=["sync"])


class ApplyIn(BaseModel):
    swing_id: int
    shot_id: int


class UnlinkIn(BaseModel):
    swing_id: int


def _proposal_dict(p):
    return {"swing_id": p.swing_id, "shot_id": p.shot_id,
            "confidence": p.confidence, "reason": p.reason}


@router.get("/proposals")
def proposals(session: int, conn=Depends(get_conn)):
    service = SyncService(conn)
    swings = repo.list_unmatched_swings(conn, session_id=session)
    shots = repo.list_unmatched_shots(conn, session_id=session)
    players = {sw.player_id for sw in swings} | {sh.player_id for sh in shots}
    props = []
    for player_id in (pid for pid in players if pid is not None):
        props.extend(service.propose_matches(session_id=session,
                                              player_id=player_id))
    props.sort(key=lambda p: p.confidence, reverse=True)
    return {
        "session": session,
        "proposals": [_proposal_dict(p) for p in props],
        "unmatched_swings": [swing_dict(sw) for sw in swings],
        "unmatched_shots": [shot_dict(sh) for sh in shots],
    }


@router.post("/apply")
def apply(body: ApplyIn, conn=Depends(get_conn)):
    SyncService(conn).apply_match(swing_id=body.swing_id, shot_id=body.shot_id)
    return {"ok": True}


@router.post("/unlink")
def unlink(body: UnlinkIn, conn=Depends(get_conn)):
    SyncService(conn).unlink(swing_id=body.swing_id)
    return {"ok": True}
```

- [ ] **Step 4: Wire the router into `app.py`**

Add `from web.backend import api_sync` and `app.include_router(api_sync.router)`.

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_api_sync.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/api_sync.py web/backend/app.py web/backend/tests/test_api_sync.py
git commit -m "feat(web): sync API (proposals/apply/unlink)"
```

---

## Task 9: SSE events + store-polling watcher

The `SwingWatcher` is a pure store query: "swings that are READY (have metrics AND coaching) with id greater than the last id I emitted." Test it by seeding, NOT by sleeping. The SSE route formats watcher results as `text/event-stream`.

**Files:**
- Create: `web/backend/events.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_events.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_events.py`:
```python
import json

from store import repo
from store.models import Metric, Coaching
from web.backend.events import SwingWatcher
from web.backend.tests.conftest import seed_player, seed_ready_swing


def _bare_swing(conn, pid):
    sid = repo.get_open_session(conn, pid)
    sid = sid.id if sid else repo.create_session(conn, pid).id
    return repo.add_swing(conn, sid, pid, "v.mp4").id


def _make_ready(conn, swing_id):
    repo.save_metrics(conn, swing_id,
                      [Metric(swing_id, "tempo", "overall", 3.0, "r", "m")])
    repo.save_coaching(conn, Coaching(swing_id=swing_id, session_id=None,
                                      kind="swing",
                                      content_json=json.dumps({"headline": "ok"})))


def test_watcher_emits_only_ready_swings_once(conn):
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    watcher = SwingWatcher(conn)

    first = watcher.poll()
    assert [e["swing_id"] for e in first] == [ready.id]
    # second poll with no new ready swings -> nothing
    assert watcher.poll() == []


def test_watcher_skips_not_yet_ready_then_emits_when_ready(conn):
    p = seed_player(conn)
    pending = _bare_swing(conn, p.id)  # metrics/coaching not written yet
    watcher = SwingWatcher(conn)
    assert watcher.poll() == []  # not ready -> not emitted

    _make_ready(conn, pending)
    assert [e["swing_id"] for e in watcher.poll()] == [pending]


def test_events_endpoint_streams_swing_ready(client, conn):
    p = seed_player(conn)
    ready = seed_ready_swing(conn, p)
    # one-shot mode: ?once=1 polls a single time and closes (test-friendly)
    r = client.get("/events", params={"once": 1})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: swing_ready" in r.text
    assert f'"swing_id": {ready.id}' in r.text
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_events.py -v`
Expected: FAIL (`No module named 'web.backend.events'`).

- [ ] **Step 3: Implement `events.py`**

`web/backend/events.py`:
```python
"""SSE stream + store-polling watcher for newly-ready swings.

A swing is READY when it has at least one metric AND at least one coaching
row. The watcher remembers the highest swing id it has emitted and only
returns newly-ready swings with a larger id, so each ready swing fires once.
"""
import asyncio
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from web.backend.deps import get_conn

router = APIRouter(tags=["events"])

POLL_INTERVAL_S = 1.5

_READY_SQL = """
SELECT sw.id AS swing_id, sw.session_id, sw.player_id
FROM swing sw
WHERE sw.id > ?
  AND EXISTS (SELECT 1 FROM metric m WHERE m.swing_id = sw.id)
  AND EXISTS (SELECT 1 FROM coaching c WHERE c.swing_id = sw.id)
ORDER BY sw.id
"""


class SwingWatcher:
    def __init__(self, conn, last_id: int = 0):
        self.conn = conn
        self.last_id = last_id

    def poll(self):
        rows = self.conn.execute(_READY_SQL, (self.last_id,)).fetchall()
        events = []
        for r in rows:
            self.last_id = max(self.last_id, r["swing_id"])
            events.append({"swing_id": r["swing_id"],
                           "session_id": r["session_id"],
                           "player_id": r["player_id"]})
        return events


def _format(event: dict) -> str:
    return f"event: swing_ready\ndata: {json.dumps(event)}\n\n"


@router.get("/events")
async def events(request: Request, once: int = 0, conn=Depends(get_conn)):
    watcher = SwingWatcher(conn)

    async def gen():
        # emit any already-ready swings immediately
        for e in watcher.poll():
            yield _format(e)
        if once:
            return
        while True:
            if await request.is_disconnected():
                break
            for e in watcher.poll():
                yield _format(e)
            yield ": keep-alive\n\n"
            await asyncio.sleep(POLL_INTERVAL_S)

    return StreamingResponse(gen(), media_type="text/event-stream")
```

- [ ] **Step 4: Wire the router into `app.py`**

Add `from web.backend import events` and `app.include_router(events.router)`.

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_events.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/backend/events.py web/backend/app.py web/backend/tests/test_events.py
git commit -m "feat(web): SSE events + store-polling swing watcher"
```

---

## Task 10: Media serving (path-traversal safe)

`GET /media/{path}` streams a file from `media_root()` only, rejecting any path that escapes the root.

**Files:**
- Create: `web/backend/media.py`
- Modify: `web/backend/app.py` (include router)
- Create: `web/backend/tests/test_media.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_media.py`:
```python
def test_serves_existing_file(client):
    (client.media_dir / "swings").mkdir()
    f = client.media_dir / "swings" / "annotated.mp4"
    f.write_bytes(b"\x00\x01fakevideo")
    r = client.get("/media/swings/annotated.mp4")
    assert r.status_code == 200
    assert r.content == b"\x00\x01fakevideo"


def test_missing_file_404(client):
    assert client.get("/media/nope.mp4").status_code == 404


def test_rejects_parent_traversal(client, tmp_path):
    # a secret outside the media root
    secret = client.media_dir.parent / "secret.txt"
    secret.write_text("top secret")
    r = client.get("/media/../secret.txt")
    assert r.status_code in (400, 404)
    assert "top secret" not in r.text


def test_rejects_encoded_traversal(client):
    r = client.get("/media/%2e%2e/secret.txt")
    assert r.status_code in (400, 404)
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_media.py -v`
Expected: FAIL (404/route missing or no guard).

- [ ] **Step 3: Implement `media.py`**

`web/backend/media.py`:
```python
"""Path-traversal-safe media file serving from the media root."""
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from web.backend.deps import media_root

router = APIRouter(tags=["media"])


@router.get("/media/{path:path}")
def get_media_file(path: str, root: Path = Depends(media_root)):
    root = root.resolve()
    candidate = (root / path).resolve()
    # candidate must live strictly inside root
    if root not in candidate.parents and candidate != root:
        raise HTTPException(status_code=400, detail="invalid path")
    if not candidate.is_file():
        raise HTTPException(status_code=404, detail="not found")
    return FileResponse(str(candidate))
```

- [ ] **Step 4: Wire the router into `app.py`**

Add `from web.backend import media` and `app.include_router(media.router)`.

- [ ] **Step 5: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_media.py -v`
Expected: PASS.

> Note on encoded traversal: Starlette decodes `%2e%2e` and normalizes the
> path before matching the `{path:path}` route, so the request typically 404s
> at routing; the `resolve()` containment check is the defense-in-depth guard
> for any path that does reach the handler. The test asserts `in (400, 404)`
> to accept either outcome.

- [ ] **Step 6: Commit**

```bash
git add web/backend/media.py web/backend/app.py web/backend/tests/test_media.py
git commit -m "feat(web): path-safe media serving"
```

---

## Task 11: Static frontend mount + full backend suite

Mount the built React app (`web/frontend/dist`) at `/` so the single FastAPI origin serves the SPA. The mount must come AFTER all API/SSE/media routers and must not 500 when `dist/` is absent (dev/test before the frontend is built).

**Files:**
- Modify: `web/backend/app.py`
- Create: `web/backend/tests/test_static_mount.py`

- [ ] **Step 1: Write the failing test**

`web/backend/tests/test_static_mount.py`:
```python
def test_api_still_works_without_built_frontend(client):
    # dist/ does not exist in the test env; API must be unaffected
    assert client.get("/api/health").json() == {"status": "ok"}


def test_serves_index_when_dist_present(tmp_path, monkeypatch):
    import web.backend.app as appmod
    from fastapi.testclient import TestClient

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>GarageTEC</title>")
    monkeypatch.setattr(appmod, "frontend_dist", lambda: dist)

    app = appmod.create_app()
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        assert "GarageTEC" in r.text
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_static_mount.py -v`
Expected: FAIL (`frontend_dist` not defined / `/` not served).

- [ ] **Step 3: Finalize `app.py`**

`web/backend/app.py` (full, final form):
```python
"""GarageTEC Screen backend: REST + SSE + media + static frontend."""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from web.backend import (
    api_players, api_sessions, api_swings, api_history, api_sync, events, media,
)


def frontend_dist() -> Path:
    return Path(__file__).resolve().parents[1] / "frontend" / "dist"


def create_app() -> FastAPI:
    app = FastAPI(title="GarageTEC Screen")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    app.include_router(api_players.router)
    app.include_router(api_sessions.router)
    app.include_router(api_swings.router)
    app.include_router(api_history.router)
    app.include_router(api_sync.router)
    app.include_router(events.router)
    app.include_router(media.router)

    dist = frontend_dist()
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=str(dist), html=True),
                  name="frontend")

    return app


app = create_app()
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest web/backend/tests/test_static_mount.py -v`
Expected: PASS.

- [ ] **Step 5: Run the FULL backend + store suite**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ web/backend/ -v`
Expected: PASS (all). This is the backend done-criterion.

- [ ] **Step 6: Commit**

```bash
git add web/backend/app.py web/backend/tests/test_static_mount.py
git commit -m "feat(web): mount built frontend; full backend suite green"
```

---

## Task 12: Frontend scaffold (Vite + React)

Create the Vite app structure by hand (deterministic — no interactive `npm create`), install deps, and confirm the toolchain runs.

**Files:**
- Create: `web/frontend/package.json`
- Create: `web/frontend/vite.config.js`
- Create: `web/frontend/index.html`
- Create: `web/frontend/.gitignore`
- Create: `web/frontend/src/main.jsx`
- Create: `web/frontend/src/styles.css`

- [ ] **Step 1: Write `package.json`**

`web/frontend/package.json`:
```json
{
  "name": "garagetec-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "recharts": "^2.12.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "jsdom": "^24.1.0",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

- [ ] **Step 2: Write `vite.config.js`**

`web/frontend/vite.config.js`:
```javascript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  base: "./",
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/events": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.js"],
  },
});
```

- [ ] **Step 3: Write `index.html`, `.gitignore`, `main.jsx`, `styles.css`, `setupTests.js`**

`web/frontend/index.html`:
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GarageTEC</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`web/frontend/.gitignore`:
```
node_modules/
dist/
```

`web/frontend/src/setupTests.js`:
```javascript
import "@testing-library/jest-dom";
```

`web/frontend/src/styles.css`:
```css
:root { color-scheme: dark; font-family: system-ui, sans-serif; }
body { margin: 0; background: #0f1115; color: #e8eaed; }
a { color: #7fb4ff; }
nav { display: flex; gap: 1rem; padding: 0.75rem 1rem; background: #171a21; }
main { padding: 1rem; }
.cards { display: flex; flex-wrap: wrap; gap: 0.75rem; }
.card { background: #1c2029; border: 1px solid #2a2f3a; border-radius: 8px;
        padding: 0.75rem 1rem; min-width: 160px; }
.flag { color: #ffb454; font-size: 0.8rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid #2a2f3a; }
button { background: #2a6df4; color: #fff; border: 0; border-radius: 6px;
         padding: 0.4rem 0.7rem; cursor: pointer; }
```

`web/frontend/src/main.jsx` (router will reference pages created in Task 14; create a minimal placeholder App first so install/build can be verified, then overwrite in Task 14):
```javascript
import React from "react";
import { createRoot } from "react-dom/client";
import "./styles.css";

function Boot() {
  return <main><h1>GarageTEC</h1><p>Loading…</p></main>;
}

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <Boot />
  </React.StrictMode>
);
```

- [ ] **Step 4: Install deps**

Run: `npm install --prefix web/frontend`
Expected: `added N packages` with no error.

- [ ] **Step 5: Build smoke (must succeed before adding pages)**

Run: `npm run build --prefix web/frontend`
Expected: `vite build` succeeds; `web/frontend/dist/index.html` exists.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/package.json web/frontend/vite.config.js web/frontend/index.html web/frontend/.gitignore web/frontend/src/main.jsx web/frontend/src/styles.css web/frontend/src/setupTests.js
git commit -m "chore(web): Vite + React frontend scaffold (builds)"
```

> Note: `node_modules/` and `dist/` are gitignored. Do NOT commit them.

---

## Task 13: API client + SSE hook + MetricCard (with a component test)

Build the shared data layer and the one tested component before the pages.

**Files:**
- Create: `web/frontend/src/api.js`
- Create: `web/frontend/src/useEvents.js`
- Create: `web/frontend/src/components/MetricCard.jsx`
- Create: `web/frontend/src/components/MetricCard.test.jsx`

- [ ] **Step 1: Write the failing component test**

`web/frontend/src/components/MetricCard.test.jsx`:
```javascript
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import MetricCard from "./MetricCard";

describe("MetricCard", () => {
  it("renders value, unit, and vs-baseline / vs-ideal", () => {
    render(
      <MetricCard
        name="hip_sway_in"
        value={2.5}
        unit="in"
        vsBaseline={+0.4}
        vsIdeal={-0.6}
      />
    );
    expect(screen.getByText("hip_sway_in")).toBeInTheDocument();
    expect(screen.getByText(/2\.5/)).toBeInTheDocument();
    expect(screen.getByText(/in/)).toBeInTheDocument();
    expect(screen.getByText(/baseline/i)).toBeInTheDocument();
    expect(screen.getByText(/ideal/i)).toBeInTheDocument();
  });

  it("shows a low-confidence flag when confidence is low", () => {
    render(<MetricCard name="tempo" value={3.1} unit="r" lowConfidence />);
    expect(screen.getByText(/low confidence/i)).toBeInTheDocument();
  });

  it("omits the flag when confidence is fine", () => {
    render(<MetricCard name="tempo" value={3.1} unit="r" />);
    expect(screen.queryByText(/low confidence/i)).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npm run test --prefix web/frontend`
Expected: FAIL (cannot resolve `./MetricCard`).

- [ ] **Step 3: Implement `MetricCard.jsx`, `api.js`, `useEvents.js`**

`web/frontend/src/components/MetricCard.jsx`:
```javascript
function delta(label, v) {
  if (v === undefined || v === null) return null;
  const sign = v > 0 ? "+" : "";
  return (
    <div className="delta">
      {label}: {sign}
      {v}
    </div>
  );
}

export default function MetricCard({
  name,
  value,
  unit,
  vsBaseline,
  vsIdeal,
  lowConfidence,
}) {
  return (
    <div className="card">
      <div className="card-name">{name}</div>
      <div className="card-value">
        {value} {unit}
      </div>
      {delta("vs baseline", vsBaseline)}
      {delta("vs ideal", vsIdeal)}
      {lowConfidence && <div className="flag">low confidence</div>}
    </div>
  );
}
```

`web/frontend/src/api.js`:
```javascript
async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

async function postJSON(url, body) {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json();
}

export const getPlayers = () => getJSON("/api/players");
export const createPlayer = (p) => postJSON("/api/players", p);
export const getSessions = (player) =>
  getJSON("/api/sessions" + (player ? `?player=${player}` : ""));
export const getSession = (id) => getJSON(`/api/sessions/${id}`);
export const getSwing = (id) => getJSON(`/api/swings/${id}`);
export const getHistory = (player, metric, context = "overall") =>
  getJSON(
    `/api/history?player=${player}&metric=${encodeURIComponent(
      metric
    )}&context=${encodeURIComponent(context)}`
  );
export const getProposals = (session) =>
  getJSON(`/api/sync/proposals?session=${session}`);
export const applyMatch = (swing_id, shot_id) =>
  postJSON("/api/sync/apply", { swing_id, shot_id });
export const unlinkSwing = (swing_id) =>
  postJSON("/api/sync/unlink", { swing_id });
export const mediaUrl = (path) => `/media/${path}`;
```

`web/frontend/src/useEvents.js`:
```javascript
import { useEffect, useState } from "react";

// Subscribes to the SSE stream; returns the latest swing_ready payload
// ({ swing_id, session_id, player_id }) or null before the first event.
export default function useEvents() {
  const [lastSwing, setLastSwing] = useState(null);

  useEffect(() => {
    const es = new EventSource("/events");
    es.addEventListener("swing_ready", (e) => {
      try {
        setLastSwing(JSON.parse(e.data));
      } catch {
        /* ignore malformed frame */
      }
    });
    return () => es.close();
  }, []);

  return lastSwing;
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `npm run test --prefix web/frontend`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/api.js web/frontend/src/useEvents.js web/frontend/src/components/
git commit -m "feat(web): API client, SSE hook, tested MetricCard"
```

---

## Task 14: The six pages + router

Concise but real JSX for each screen, wired to the API client + SSE hook. No placeholder comments.

**Files:**
- Create: `web/frontend/src/pages/Live.jsx`
- Create: `web/frontend/src/pages/SwingReview.jsx`
- Create: `web/frontend/src/pages/Session.jsx`
- Create: `web/frontend/src/pages/History.jsx`
- Create: `web/frontend/src/pages/SyncFix.jsx`
- Create: `web/frontend/src/pages/Players.jsx`
- Create: `web/frontend/src/App.jsx`
- Modify: `web/frontend/src/main.jsx` (use the real App + router)

- [ ] **Step 1: Write the pages**

`web/frontend/src/pages/Live.jsx`:
```javascript
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import useEvents from "../useEvents";
import { getSwing, mediaUrl } from "../api";
import MetricCard from "../components/MetricCard";

export default function Live() {
  const lastSwing = useEvents();
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    if (lastSwing?.swing_id) getSwing(lastSwing.swing_id).then(setDetail);
  }, [lastSwing]);

  if (!detail) return <main><h1>Waiting for the next swing…</h1></main>;

  const { swing, metrics, shot, coaching, media } = detail;
  const video = media.find((m) => m.kind === "annotated_video");
  const read = coaching[0]?.content || {};

  return (
    <main>
      <h1>
        Last swing · {swing.club || "—"}{" "}
        <Link to={`/swing/${swing.id}`}>review →</Link>
      </h1>
      {video && (
        <video src={mediaUrl(video.path)} controls width={640} />
      )}
      {read.headline && <h2>{read.headline}</h2>}
      <div className="cards">
        {metrics.map((m) => (
          <MetricCard
            key={m.id}
            name={m.name}
            value={m.value}
            unit={m.unit}
            lowConfidence={m.method === "estimate"}
          />
        ))}
      </div>
      {shot && (
        <p>
          Ball {shot.ball_speed} mph · carry {shot.carry} · VLA {shot.vla}
        </p>
      )}
      {read.drills?.length > 0 && (
        <>
          <h3>Drills</h3>
          <ul>{read.drills.map((d, i) => <li key={i}>{d}</li>)}</ul>
        </>
      )}
    </main>
  );
}
```

`web/frontend/src/pages/SwingReview.jsx`:
```javascript
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { getSwing, mediaUrl } from "../api";

export default function SwingReview() {
  const { id } = useParams();
  const [detail, setDetail] = useState(null);

  useEffect(() => {
    getSwing(id).then(setDetail);
  }, [id]);

  if (!detail) return <main><p>Loading swing…</p></main>;
  const { swing, metrics, moments, shot, coaching, media } = detail;
  const video = media.find((m) => m.kind === "annotated_video");
  const read = coaching[0]?.content || {};

  return (
    <main>
      <h1>Swing #{swing.id} · {swing.club || "—"}</h1>
      {video && <video src={mediaUrl(video.path)} controls width={720} />}

      <h3>Phases</h3>
      <ol>
        {moments.map((m) => (
          <li key={m.id}>
            {m.kind} — frame {m.frame_index} ({m.time_s}s)
          </li>
        ))}
      </ol>

      <h3>Metrics</h3>
      <table>
        <thead>
          <tr><th>Metric</th><th>Context</th><th>Value</th><th>Method</th></tr>
        </thead>
        <tbody>
          {metrics.map((m) => (
            <tr key={m.id}>
              <td>{m.name}</td><td>{m.context}</td>
              <td>{m.value} {m.unit}</td><td>{m.method}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {shot && (
        <>
          <h3>Matched shot</h3>
          <p>
            Ball {shot.ball_speed} · spin {shot.total_spin} · carry {shot.carry}
          </p>
        </>
      )}

      {read.headline && (
        <>
          <h3>Coach</h3>
          <p>{read.headline}</p>
          <ul>{(read.findings || []).map((f, i) => <li key={i}>{f}</li>)}</ul>
        </>
      )}
    </main>
  );
}
```

`web/frontend/src/pages/Session.jsx`:
```javascript
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSession } from "../api";

export default function Session() {
  const { id } = useParams();
  const [data, setData] = useState(null);

  useEffect(() => {
    getSession(id).then(setData);
  }, [id]);

  if (!data) return <main><p>Loading session…</p></main>;
  const { session, swings, coaching } = data;
  const summary = coaching.find((c) => c.kind === "session")?.content;

  return (
    <main>
      <h1>Session #{session.id} · {session.location || "—"}</h1>
      {summary?.headline && <p>{summary.headline}</p>}
      <h3>Swings ({swings.length})</h3>
      <table>
        <thead><tr><th>#</th><th>Club</th><th>Matched</th><th></th></tr></thead>
        <tbody>
          {swings.map((s) => (
            <tr key={s.id}>
              <td>{s.id}</td><td>{s.club || "—"}</td>
              <td>{s.shot_id ? "yes" : "no"}</td>
              <td><Link to={`/swing/${s.id}`}>review</Link></td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
```

`web/frontend/src/pages/History.jsx`:
```javascript
import { useEffect, useState } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid, ResponsiveContainer,
} from "recharts";
import { getPlayers, getHistory } from "../api";

export default function History() {
  const [players, setPlayers] = useState([]);
  const [player, setPlayer] = useState("");
  const [metric, setMetric] = useState("hip_sway_in");
  const [context, setContext] = useState("impact");
  const [points, setPoints] = useState([]);

  useEffect(() => {
    getPlayers().then((ps) => {
      setPlayers(ps);
      if (ps[0]) setPlayer(String(ps[0].id));
    });
  }, []);

  useEffect(() => {
    if (player) getHistory(player, metric, context).then((d) => setPoints(d.points));
  }, [player, metric, context]);

  return (
    <main>
      <h1>History</h1>
      <div>
        <select value={player} onChange={(e) => setPlayer(e.target.value)}>
          {players.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <input value={metric} onChange={(e) => setMetric(e.target.value)} />
        <input value={context} onChange={(e) => setContext(e.target.value)} />
      </div>
      <div style={{ width: "100%", height: 320 }}>
        <ResponsiveContainer>
          <LineChart data={points}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="created_at" hide />
            <YAxis />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#7fb4ff" />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </main>
  );
}
```

`web/frontend/src/pages/SyncFix.jsx`:
```javascript
import { useEffect, useState } from "react";
import { getSessions, getProposals, applyMatch, unlinkSwing } from "../api";

export default function SyncFix() {
  const [sessions, setSessions] = useState([]);
  const [session, setSession] = useState("");
  const [data, setData] = useState(null);

  useEffect(() => {
    getSessions().then((ss) => {
      setSessions(ss);
      if (ss[0]) setSession(String(ss[0].id));
    });
  }, []);

  const refresh = (sid) => getProposals(sid).then(setData);
  useEffect(() => {
    if (session) refresh(session);
  }, [session]);

  async function onApply(swing_id, shot_id) {
    await applyMatch(swing_id, shot_id);
    refresh(session);
  }
  async function onUnlink(swing_id) {
    await unlinkSwing(swing_id);
    refresh(session);
  }

  return (
    <main>
      <h1>Sync fix</h1>
      <select value={session} onChange={(e) => setSession(e.target.value)}>
        {sessions.map((s) => (
          <option key={s.id} value={s.id}>Session {s.id}</option>
        ))}
      </select>

      <h3>Proposals</h3>
      <table>
        <thead>
          <tr><th>Swing</th><th>Shot</th><th>Confidence</th><th></th></tr>
        </thead>
        <tbody>
          {(data?.proposals || []).map((p) => (
            <tr key={`${p.swing_id}-${p.shot_id}`}>
              <td>{p.swing_id}</td><td>{p.shot_id}</td>
              <td>{p.confidence.toFixed(2)}</td>
              <td>
                <button onClick={() => onApply(p.swing_id, p.shot_id)}>
                  confirm
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h3>Unmatched swings</h3>
      <ul>
        {(data?.unmatched_swings || []).map((s) => (
          <li key={s.id}>
            Swing {s.id}{" "}
            <button onClick={() => onUnlink(s.id)}>unlink</button>
          </li>
        ))}
      </ul>
    </main>
  );
}
```

`web/frontend/src/pages/Players.jsx`:
```javascript
import { useEffect, useState } from "react";
import { getPlayers, createPlayer } from "../api";

export default function Players() {
  const [players, setPlayers] = useState([]);
  const [name, setName] = useState("");
  const [heightIn, setHeightIn] = useState("70");
  const [handedness, setHandedness] = useState("R");

  const load = () => getPlayers().then(setPlayers);
  useEffect(() => {
    load();
  }, []);

  async function onAdd(e) {
    e.preventDefault();
    if (!name) return;
    await createPlayer({
      name,
      height_in: parseFloat(heightIn),
      handedness,
    });
    setName("");
    load();
  }

  return (
    <main>
      <h1>Players</h1>
      <ul>
        {players.map((p) => (
          <li key={p.id}>
            {p.name} · {p.height_in}in · {p.handedness}
          </li>
        ))}
      </ul>
      <form onSubmit={onAdd}>
        <input
          placeholder="Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <input
          placeholder="Height (in)"
          value={heightIn}
          onChange={(e) => setHeightIn(e.target.value)}
        />
        <select value={handedness} onChange={(e) => setHandedness(e.target.value)}>
          <option value="R">R</option>
          <option value="L">L</option>
        </select>
        <button type="submit">Add player</button>
      </form>
    </main>
  );
}
```

- [ ] **Step 2: Write `App.jsx` and update `main.jsx`**

`web/frontend/src/App.jsx`:
```javascript
import { Routes, Route, Link } from "react-router-dom";
import Live from "./pages/Live";
import SwingReview from "./pages/SwingReview";
import Session from "./pages/Session";
import History from "./pages/History";
import SyncFix from "./pages/SyncFix";
import Players from "./pages/Players";

export default function App() {
  return (
    <>
      <nav>
        <Link to="/">Live</Link>
        <Link to="/history">History</Link>
        <Link to="/sync">Sync fix</Link>
        <Link to="/players">Players</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Live />} />
        <Route path="/swing/:id" element={<SwingReview />} />
        <Route path="/session/:id" element={<Session />} />
        <Route path="/history" element={<History />} />
        <Route path="/sync" element={<SyncFix />} />
        <Route path="/players" element={<Players />} />
      </Routes>
    </>
  );
}
```

`web/frontend/src/main.jsx` (overwrite the Task 12 placeholder):
```javascript
import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App";
import "./styles.css";

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);
```

- [ ] **Step 3: Build smoke (the pages must compile)**

Run: `npm run build --prefix web/frontend`
Expected: `vite build` succeeds; `web/frontend/dist/index.html` regenerated.

- [ ] **Step 4: Component tests still pass**

Run: `npm run test --prefix web/frontend`
Expected: PASS (MetricCard suite).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/App.jsx web/frontend/src/main.jsx web/frontend/src/pages/
git commit -m "feat(web): six React pages + router (builds)"
```

> Deferred per spec section 9: deep UI/interaction testing of the pages.
> Coverage here is the build smoke + the MetricCard component test only.

---

## Task 15: End-to-end serve check + final verification

Confirm the built frontend is served by FastAPI single-origin and the whole suite is green.

**Files:** (none new — verification only)

- [ ] **Step 1: Build the frontend**

Run: `npm run build --prefix web/frontend`
Expected: `web/frontend/dist/index.html` exists.

- [ ] **Step 2: Run the full Python suite (now with `dist/` present)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ web/backend/ -v`
Expected: PASS (all). `test_static_mount` exercises the served SPA path.

- [ ] **Step 3: Manual smoke (optional, not a test gate)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m uvicorn web.backend.app:app --host 0.0.0.0 --port 8000`
Then browse `http://localhost:8000/` (SPA), `http://localhost:8000/api/players` (JSON), `http://localhost:8000/api/health`. Stop with Ctrl+C.

- [ ] **Step 4: Commit the built assets decision**

`dist/` is gitignored (built on deploy). If the deployment model instead requires committing built assets to the repo, remove `dist/` from `web/frontend/.gitignore` and commit `web/frontend/dist/`. Default: keep it ignored.

```bash
git add web/frontend/.gitignore
git commit -m "chore(web): document frontend build/serve flow"
```

---

## Done criteria

- `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest store/ web/backend/ -v` is fully green (store additions + every backend router + watcher + media).
- Backend covers all spec section 6 endpoints: `GET/POST /api/players`, `GET /api/sessions(?player=)`, `GET /api/sessions/{id}`, `GET /api/swings/{id}` (aggregate), `GET /api/history`, `GET /api/sync/proposals?session=`, `POST /api/sync/apply`, `POST /api/sync/unlink`, `GET /events` (SSE), `GET /media/{path}` (path-safe).
- The SSE watcher is tested by seeding the store (ready = has metrics AND coaching), never by wall-clock sleeps.
- `npm run build --prefix web/frontend` succeeds; `npm run test --prefix web/frontend` passes (MetricCard).
- The six pages exist and compile; FastAPI serves the built SPA single-origin (no CORS).
- Store gains `list_sessions` and `get_session` (with tests); `get_shot` already exists (from the AI coach rock) and is reused.
- Deep UI testing explicitly deferred (spec section 9).
```

