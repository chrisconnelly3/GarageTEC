# Phase 3 Polish — Settings Persistence, History Filter, Player Swing-Count, Review Swing-Picker

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finish the four items Phase 2 left local-only / visual-only in the GarageTEC unified app (`web/backend/` + `web/frontend/`):

1. **Connect settings persistence** — a `settings` table + `GET/PUT /api/settings`; the `CaptureSupervisor` reads `idle_minutes` (idle-session sweep) and `port` (listener bind) from settings on start/restart; `units` is a stored frontend display preference. Wire the Connect screen's settings form to load + save.
2. **History timeframe filter** — make the Session/Week/Month/Year pill actually filter the `GET /api/history` points client-side by `created_at`.
3. **Players real swing-count** — add a real per-player `swing_count` (keep `session_count`) to `GET /api/players`; show it on the Players page.
4. **Review swing-picker** — `GET /api/swings?player=&session=&limit=` returning swing summaries; add a selector to the Review screen (default = latest).

**Methodology:** frontend-pragmatic — **TDD for the backend additions** (settings get/save, the players-with-counts shape, the swings list endpoint: failing test → impl → pass), **pragmatic for the frontend** (wire + build; no per-component TDD). Gates: backend `pytest` green (incl. new tests), frontend `npm run build` (tsc + vite) + `npm run test` (vitest) green, and a **run-and-verify** note (seed + uvicorn + browser).

**Tech stack (unchanged):** React 18 · TypeScript (strict, `noUnusedLocals/Parameters: false`) · Vite 5 · Tailwind 3 · framer-motion · lucide-react · recharts · vitest. Backend: FastAPI + sqlite `store/`. Full Python path (py launcher NOT on PATH): `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`. Node/npm at `C:\Program Files\nodejs`.

---

## SCOPE — read before starting

**IN SCOPE (Phase 3, exactly these 4):** the four items above and nothing else.

**OUT OF SCOPE:**
- No new visual components, no redesign. Reuse existing components; only data wiring + the two new UI affordances (Connect save button behavior, Review swing selector) change.
- No change to the capture/pose/metrics/coach pipeline beyond having the supervisor READ `idle_minutes`/`port` from settings.
- `units` does NOT trigger any value re-computation; it is stored and read back. Actually converting yards↔meters across screens is not in scope (note in report).
- No auth, no multi-user settings (single global settings row).

---

## Current state (verified against source — what exists today)

### Backend shapes that already exist (do not change)
- `store/db.py` — `init_db()` runs `schema.sql` via `executescript`; `now_iso()`; `default_db_path()`. `SCHEMA_VERSION = 1`.
- `store/schema.sql` — all tables use `CREATE TABLE IF NOT EXISTS` (auto-creates on every `init_db`). **No `settings` table yet.**
- `store/repo.py` — has `list_players`, `get_player`, `list_sessions(conn, player_id=None)`, `list_swings(conn, session_id=None, limit=None)`, `get_metrics`, `get_shot`, `get_coaching`, `swing_history(conn, player, metric, context="overall")`, etc. **No settings or count helpers yet.**
- `web/backend/serializers.py` — `player_dict`, `swing_dict`, `metric_dict`, `shot_dict`, `coaching_dict`, etc.
- `web/backend/api_players.py` — `GET /api/players` → `[player_dict(p) for p in repo.list_players(conn)]`; `POST /api/players`.
- `web/backend/api_history.py` — `GET /api/history?player&metric&context` (default `"overall"` — but the frontend always passes `"impact"`). Returns `{player, metric, context, points: [{swing_id, created_at, value}]}`.
- `web/backend/api_swings.py` — `GET /api/swings/latest?player&session` (204 when none) and `GET /api/swings/{id}`. **No list endpoint.** Router prefix is `/api/swings`. **Route ordering matters:** `/latest` is declared BEFORE `/{swing_id}`; the new `GET /api/swings` (empty path) is fine since `{swing_id}` only matches a path segment.
- `web/backend/deps.py` — `get_conn()` (request-scoped store conn, runs `init_db`), `_listener_conn()` (dedicated listener conn), `capture_bus()` + `get_supervisor()` singletons. **`get_supervisor()` constructs `CaptureSupervisor(conn=_listener_conn(), bus=capture_bus())` with NO `idle_minutes`/`port` args** — so today they come purely from the `__init__` defaults.

### Where the supervisor gets `idle_minutes` / `port` TODAY (critical)
`web/backend/capture.py` `CaptureSupervisor.__init__(..., port=PORT_DEFAULT, idle_minutes=15, ...)`:
- `idle_minutes` → passed into `self.session_mgr = SessionManager(conn, idle_minutes=idle_minutes)` (used by `SessionManager.sweep_idle` → `repo.end_idle_sessions`).
- `port` → stored as `self.port`, used in `_spawn_listener()` (`port=self.port`). `restart()` calls `_spawn_listener()` again, so **changing `self.port` then calling `restart()` rebinds on the new port.**

`deps.get_supervisor()` does not pass either, so both use the hardcoded defaults today. **Phase 3 makes `get_supervisor()` read them from settings at construction, and makes `/api/capture/restart` re-read `port` + `idle_minutes` from settings before restarting.**

### Frontend state today
- `web/frontend/src/lib/api.ts` — typed fns for every existing endpoint. **No `getSettings`/`putSettings`/`getSwings`.** `getPlayers()` returns `Player[]`.
- `web/frontend/src/lib/types.ts` — `Player` is `{id,name,height_in,handedness,created_at}` (no counts). No `Settings`/`SwingSummary`.
- `web/frontend/src/pages/ConnectScreen.tsx` — settings inputs (`idleTimeout`, `units`, `port`) are local `useState` with `// Phase 3: persist…` notes. No Save button wired.
- `web/frontend/src/pages/HistoryScreen.tsx` — `timeframe` state exists; the pill is visual-only (`// Phase 3: server-side timeframe filtering; visual-only for now`). `hero.points` is mapped straight to `chartData`.
- `web/frontend/src/pages/PlayersScreen.tsx` — `PlayerVM` shows `sessions` (from `getSessions(p.id).length`) and `lastActive`. No swing count.
- `web/frontend/src/pages/ReviewScreen.tsx` — takes `swingId: number | null` (App resolves the latest ready swing id). No picker.
- `web/frontend/src/App.tsx` — owns `activePlayerId`, `activeSessionId`, `reviewSwingId` (latest ready swing). Passes `swingId={reviewSwingId}` to `ReviewScreen`.

### Test fixtures available
- `store/tests/conftest.py` → `db` fixture (in-memory conn, `init_db` applied).
- `web/backend/tests/conftest.py` → `conn`, `bus`, `supervisor`, `client` fixtures + `seed_player(conn, ...)`, `seed_ready_swing(conn, player, *, club=...)` helpers.

---

## Settings contract (NEW — the shapes you wire to)

`GET /api/settings` → **`Settings`** = `{ idle_minutes: int, units: "yards"|"meters", port: int }`
`PUT /api/settings` body = partial or full `{ idle_minutes?, units?, port? }` → the FULL `Settings` after merge.

**Defaults** (used when no row / a field is unset): `idle_minutes=15`, `units="yards"`, `port=921`.

Storage: a single-row key/value `settings` table (`key TEXT PRIMARY KEY, value TEXT`). `get_settings` reads all rows, coerces types, fills defaults. `save_settings` upserts only the provided keys. Strings stored; ints/units parsed on read.

---

## File plan

```
store/
  schema.sql                         # EDIT (Task 1) — add settings table (IF NOT EXISTS)
  repo.py                            # EDIT (Task 1,3,4) — get_settings/save_settings; count helpers; list_swing_summaries
  tests/test_settings.py             # NEW (Task 1) — repo settings TDD
  tests/test_players.py              # EDIT (Task 3) — count helper TDD
  tests/test_swings.py               # EDIT (Task 4) — list_swing_summaries TDD
web/backend/
  api_settings.py                    # NEW (Task 2) — GET/PUT /api/settings
  app.py                             # EDIT (Task 2) — include api_settings.router
  deps.py                            # EDIT (Task 2) — get_supervisor reads settings
  capture.py                         # EDIT (Task 2) — apply_settings() to re-read idle/port on restart
  api_capture.py                     # EDIT (Task 2) — restart re-reads settings
  api_players.py                     # EDIT (Task 3) — return swing_count + session_count
  api_swings.py                      # EDIT (Task 4) — add GET /api/swings (list)
  serializers.py                     # EDIT (Task 4) — swing_summary_dict
  tests/test_api_settings.py         # NEW (Task 2) — endpoint TDD + supervisor-reads-settings
  tests/test_api_players.py          # EDIT (Task 3) — assert counts
  tests/test_api_swings.py           # EDIT (Task 4) — assert list endpoint
web/frontend/src/
  lib/types.ts                       # EDIT — Settings, SwingSummary, PlayerWithCounts
  lib/api.ts                         # EDIT — getSettings/putSettings/getSwings; getPlayers type
  lib/format.ts                      # EDIT (Task 5) — withinTimeframe helper (+ unit test)
  lib/api.test.ts                    # EDIT (Task 6) — withinTimeframe unit test
  pages/ConnectScreen.tsx            # EDIT (Task 2) — load/save settings
  pages/HistoryScreen.tsx            # EDIT (Task 5) — filter points by timeframe
  pages/PlayersScreen.tsx            # EDIT (Task 3) — show swing_count
  pages/ReviewScreen.tsx             # EDIT (Task 4) — swing selector
  App.tsx                            # EDIT (Task 4) — pass playerId/sessionId to Review for the picker
```
`node_modules/` and `dist/` stay gitignored (already in `web/frontend/.gitignore`). Never stage them.

---

## Tasks

### Task 1 — Settings store: schema + `get_settings`/`save_settings` (TDD)

**Failing test first.** Create `store/tests/test_settings.py`:

```python
from store import repo


def test_get_settings_returns_defaults_when_empty(db):
    s = repo.get_settings(db)
    assert s == {"idle_minutes": 15, "units": "yards", "port": 921}


def test_save_settings_upserts_and_merges(db):
    repo.save_settings(db, {"idle_minutes": 30, "port": 922})
    s = repo.get_settings(db)
    assert s["idle_minutes"] == 30 and s["port"] == 922
    assert s["units"] == "yards"  # untouched default
    # partial update overwrites only provided keys
    repo.save_settings(db, {"units": "meters"})
    s2 = repo.get_settings(db)
    assert s2 == {"idle_minutes": 30, "units": "meters", "port": 922}


def test_get_settings_coerces_types(db):
    repo.save_settings(db, {"idle_minutes": 12, "port": 5000})
    s = repo.get_settings(db)
    assert isinstance(s["idle_minutes"], int) and isinstance(s["port"], int)
```

Run it (expect failures — no table, no helpers):
`& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest store/tests/test_settings.py -q`

- [ ] Add the table to `store/schema.sql` (append after the `coaching` table, before the indexes):

```sql
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT
);
```
(`CREATE TABLE IF NOT EXISTS` → `init_db` auto-creates it on every connect; no migration/version bump needed since `init_db` always re-runs the full script.)

- [ ] Add to `store/repo.py` (near the top-level helpers, e.g. after `get_player`):

```python
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
```

- [ ] Re-run the test → green.

### Task 2 — `GET/PUT /api/settings`, supervisor reads idle/port (TDD)

**Failing test first.** Create `web/backend/tests/test_api_settings.py`:

```python
def test_get_settings_defaults(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json() == {"idle_minutes": 15, "units": "yards", "port": 921}


def test_put_settings_merges_and_returns_full(client):
    r = client.put("/api/settings", json={"idle_minutes": 25, "units": "meters"})
    assert r.status_code == 200
    body = r.json()
    assert body["idle_minutes"] == 25 and body["units"] == "meters"
    assert body["port"] == 921  # untouched
    # persisted on a subsequent GET
    assert client.get("/api/settings").json()["idle_minutes"] == 25


def test_put_settings_rejects_bad_units(client):
    r = client.put("/api/settings", json={"units": "furlongs"})
    assert r.status_code == 422


def test_restart_applies_settings_port_and_idle(client, conn):
    # change port + idle, restart; supervisor must pick up both
    client.put("/api/settings", json={"port": 9999, "idle_minutes": 7})
    client.post("/api/capture/restart")
    sup = client.supervisor
    assert sup.port == 9999
    assert sup.session_mgr.idle_minutes == 7
```

> The `client` fixture overrides `get_conn` and `get_supervisor` with a shared in-memory `conn` and the test `supervisor`. The settings endpoints use `get_conn` (so they hit the same in-memory conn). For `test_restart_applies_settings_*`, `api_capture.restart` must read settings via a conn and call `sup.apply_settings(...)` — see wiring below. The test supervisor is constructed by the fixture (no idle/port), and `restart()` will now re-read from settings.

Run it (expect failures):
`& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/tests/test_api_settings.py -q`

- [ ] Create `web/backend/api_settings.py`:

```python
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from store import repo
from web.backend.deps import get_conn

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    idle_minutes: Optional[int] = None
    units: Optional[str] = None
    port: Optional[int] = None


@router.get("")
def get_settings(conn=Depends(get_conn)):
    return repo.get_settings(conn)


@router.put("")
def put_settings(body: SettingsIn, conn=Depends(get_conn)):
    values = {k: v for k, v in body.model_dump().items() if v is not None}
    if "units" in values and values["units"] not in ("yards", "meters"):
        raise HTTPException(status_code=422, detail="units must be yards|meters")
    if "idle_minutes" in values and values["idle_minutes"] < 1:
        raise HTTPException(status_code=422, detail="idle_minutes must be >= 1")
    if "port" in values and not (1 <= values["port"] <= 65535):
        raise HTTPException(status_code=422, detail="port out of range")
    return repo.save_settings(conn, values)
```

- [ ] Register the router in `web/backend/app.py` (add the import and an `include_router`):
  - Add `api_settings` to the `from web.backend import (...)` tuple.
  - Add `app.include_router(api_settings.router)` alongside the other routers.

- [ ] Add `apply_settings` to `web/backend/capture.py` `CaptureSupervisor` (so idle/port can be (re)applied from a settings dict). Insert near `set_active_player`:

```python
def apply_settings(self, settings: dict):
    """Adopt idle_minutes + port from a settings dict. idle takes effect
    immediately (next sweep); port takes effect on the next listener spawn
    (i.e. restart())."""
    if "idle_minutes" in settings:
        self.session_mgr.idle_minutes = int(settings["idle_minutes"])
    if "port" in settings:
        self.port = int(settings["port"])
```

- [ ] Make `web/backend/api_capture.py restart` re-read settings then restart. Edit the `restart` route to also depend on `get_conn` and apply settings before `sup.restart()`:

```python
from web.backend.deps import get_conn, get_supervisor  # get_conn added
from store import repo  # added

@router.post("/restart")
def restart(sup=Depends(get_supervisor), conn=Depends(get_conn)):
    sup.apply_settings(repo.get_settings(conn))
    sup.restart()
    return {"ok": True, **_status_dict(sup)}
```

- [ ] Make `deps.get_supervisor()` seed the supervisor from settings at construction (so a fresh boot honors persisted idle/port). Edit `get_supervisor`:

```python
def get_supervisor() -> CaptureSupervisor:
    global _supervisor
    if _supervisor is None:
        conn = _listener_conn()
        settings = repo.get_settings(conn)
        _supervisor = CaptureSupervisor(
            conn=conn, bus=capture_bus(),
            port=settings["port"], idle_minutes=settings["idle_minutes"])
    return _supervisor
```
  - Add `from store import repo` to `deps.py` imports.

> Why both construction AND restart read settings: construction covers a fresh process boot (uvicorn start); `restart()` covers a live port change from the Connect screen via the existing `POST /api/capture/restart`. The fixture-built test supervisor is constructed without these args, which is fine — `test_restart_applies_settings_*` exercises the `restart()` path.

- [ ] Re-run the settings tests → green.

- [ ] **Wire the Connect screen** (`web/frontend/src/pages/ConnectScreen.tsx`):
  - Add to `lib/types.ts`: `export interface Settings { idle_minutes: number; units: "yards" | "meters"; port: number; }`
  - Add to `lib/api.ts`:
    ```ts
    import type { Settings } from "./types"; // extend the existing import
    export const getSettings = () => getJSON<Settings>("/api/settings");
    export const putSettings = (s: Partial<Settings>) => putJSON<Settings>("/api/settings", s);
    ```
    and add a `putJSON` next to `postJSON`:
    ```ts
    async function putJSON<T>(url: string, body: unknown): Promise<T> {
      const r = await fetch(url, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!r.ok) throw new Error(`${r.status} ${url}`);
      return r.json() as Promise<T>;
    }
    ```
  - In `ConnectScreen.tsx`, replace the three `useState` initializers with values loaded from `getSettings`, and add a Save button. Concretely:
    - `const { data: settings } = useApi(getSettings, [])` (import `useApi`, `getSettings`, `putSettings`).
    - Seed local state from `settings` once loaded: a `useEffect(() => { if (settings) { setIdleTimeout(String(settings.idle_minutes)); setUnits(settings.units === "meters" ? "Meters" : "Yards"); setPort(String(settings.port)); } }, [settings])`.
    - Add a `saving`/`saved` flag and a Save button at the bottom of the settings card:
      ```tsx
      const [saved, setSaved] = useState(false)
      const onSave = () => {
        putSettings({
          idle_minutes: parseInt(idleTimeout || '15', 10) || 15,
          units: units === 'Meters' ? 'meters' : 'yards',
          port: parseInt(port || '921', 10) || 921,
        }).then(() => { setSaved(true); setTimeout(() => setSaved(false), 2000) })
          .catch(() => {})
      }
      ```
      Render a button (reuse the existing green button classes from PlayersScreen's Add button) labeled `Save Settings` / `Saved ✓` when `saved`. Keep all existing input markup; only remove the two `// Phase 3:` notes.
  - Remove the `// Phase 3: persist via …` comments now that it persists.
  - **Note:** changing `port` here does NOT auto-restart the listener. Add a small helper line under the Port input or in the Save handler that, when the port changed, also calls `restartCapture()` (already in `lib/api.ts`) so the new port binds. Simplest: in `onSave`, after `putSettings` resolves, if `port` differs from `settings?.port`, call `restartCapture()`. Document this in the report.

### Task 3 — Players real `swing_count` + `session_count` (TDD)

**Failing test first.** Edit `store/tests/test_players.py` — add:

```python
def test_player_swing_and_session_counts(db):
    from store import repo
    from store.models import Metric
    p = repo.get_or_create_player(db, "Cnt", 70.0, "R")
    s1 = repo.create_session(db, p.id).id
    s2 = repo.create_session(db, p.id).id
    repo.add_swing(db, s1, p.id, "a.mp4")
    repo.add_swing(db, s1, p.id, "b.mp4")
    repo.add_swing(db, s2, p.id, "c.mp4")
    assert repo.count_swings_for_player(db, p.id) == 3
    assert repo.count_sessions_for_player(db, p.id) == 2
    # a different player is isolated
    other = repo.get_or_create_player(db, "Other", 70.0, "L")
    assert repo.count_swings_for_player(db, other.id) == 0
```

Run: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest store/tests/test_players.py -q` (expect failure).

- [ ] Add to `store/repo.py`:

```python
def count_swings_for_player(conn, player_id):
    row = conn.execute("SELECT COUNT(*) c FROM swing WHERE player_id=?",
                       (player_id,)).fetchone()
    return row["c"]


def count_sessions_for_player(conn, player_id):
    row = conn.execute("SELECT COUNT(*) c FROM session WHERE player_id=?",
                       (player_id,)).fetchone()
    return row["c"]
```

- [ ] Re-run → green.

**Endpoint TDD.** Edit `web/backend/tests/test_api_players.py` — add:

```python
def test_players_include_counts(client, conn):
    from store import repo
    p = repo.get_or_create_player(conn, "Counter", 71.0, "R")
    sid = repo.create_session(conn, p.id).id
    repo.add_swing(conn, sid, p.id, "x.mp4")
    repo.add_swing(conn, sid, p.id, "y.mp4")
    body = client.get("/api/players").json()
    row = next(r for r in body if r["id"] == p.id)
    assert row["swing_count"] == 2
    assert row["session_count"] == 1
    # base player fields still present
    assert row["name"] == "Counter" and row["handedness"] == "R"
```

Run: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/tests/test_api_players.py -q` (expect failure).

- [ ] Edit `web/backend/api_players.py` `list_players` to enrich each player with counts:

```python
@router.get("")
def list_players(conn=Depends(get_conn)):
    out = []
    for p in repo.list_players(conn):
        d = player_dict(p)
        d["swing_count"] = repo.count_swings_for_player(conn, p.id)
        d["session_count"] = repo.count_sessions_for_player(conn, p.id)
        out.append(d)
    return out
```
(Keep `player_dict` untouched so `POST /api/players` and other callers are unaffected.)

- [ ] Re-run → green.

- [ ] **Wire the Players page:**
  - `lib/types.ts`: add `export interface PlayerWithCounts extends Player { swing_count: number; session_count: number; }`.
  - `lib/api.ts`: change `getPlayers` return type to `PlayerWithCounts[]`:
    ```ts
    export const getPlayers = () => getJSON<PlayerWithCounts[]>("/api/players");
    ```
    (`createPlayer` still returns `Player`. Callers that only read `id`/`name`/`height_in`/`handedness` keep compiling since `PlayerWithCounts extends Player`.)
  - `pages/PlayersScreen.tsx`: the `PlayerVM` already extends `Player` with `sessions`/`lastActive`. Now that the API returns counts directly, drop the per-player `getSessions(p.id)` fan-out and use the API fields:
    - Add `swings: number` to `PlayerVM`.
    - In the `useApi` body: `const players = await getPlayers()` (now `PlayerWithCounts[]`); map `sessions: p.session_count`, `swings: p.swing_count`. `lastActive` previously came from `getSessions(p.id)[0]`; keep ONE lazy `getSessions` per player only if you still want `lastActive`, otherwise set `lastActive: '--'` and note it. **Recommended:** keep `lastActive` by a single `getSessions(p.id)` fan-out (cheap) OR drop it to `'--'`. Pick one and note it in the report.
    - Render a third stat block in the card's stats grid (currently 2 cols: Sessions / Last Active). Change to show **Swings** and **Sessions** (the two real counts), keep **Last Active** if retained. Use the existing stat-block markup (the `text-[10px] uppercase … Sessions` block) — duplicate it for `Swings` showing `{player.swings}`.

### Task 4 — Review swing-picker: `GET /api/swings` list + selector (TDD)

**Failing store test first.** Edit `store/tests/test_swings.py` — add:

```python
def test_list_swing_summaries_enriches(db):
    import json
    from store.models import Metric, Coaching
    p = repo.get_or_create_player(db, "Sum", 70.0, "R")
    sid = repo.create_session(db, p.id).id
    sw = repo.add_swing(db, sid, p.id, "a.mp4", club="7i")
    repo.save_metrics(db, sw.id, [
        Metric(sw.id, "hip_sway_in", "impact", 2.5, "in", "ratio"),
        Metric(sw.id, "shoulder_tilt_deg", "impact", 38.0, "deg", "exact"),
    ])
    rows = repo.list_swing_summaries(db, player_id=p.id, session_id=sid, limit=10)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == sw.id and r["club"] == "7i"
    assert r["has_shot"] is False
    # a key metric surfaced (hip_sway impact)
    assert r["hip_sway_in"] == 2.5
```

Run: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest store/tests/test_swings.py -q` (expect failure).

- [ ] Add `list_swing_summaries` to `store/repo.py` (reuse `list_swings` + light per-swing enrichment):

```python
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
```

- [ ] Re-run → green.

**Endpoint TDD.** Edit `web/backend/tests/test_api_swings.py` — add:

```python
def test_list_swings_endpoint(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    r = client.get(f"/api/swings?player={p.id}")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body, list) and len(body) >= 1
    top = body[0]
    assert top["id"] == swing.id
    assert top["has_shot"] is True            # seed_ready_swing links a shot
    assert top["club"] == "7i"
    assert "created_at" in top


def test_list_swings_scoped_to_session(client, conn):
    from store import repo
    p = seed_player(conn)
    seed_ready_swing(conn, p)                  # session A
    # a swing in a different session should be excluded when session= is passed
    other_sid = repo.create_session(conn, p.id).id
    repo.add_swing(conn, other_sid, p.id, "z.mp4")
    body = client.get(f"/api/swings?player={p.id}&session={other_sid}").json()
    assert [s["id"] for s in body] == [body[0]["id"]]
    assert all(s["club"] is None for s in body)  # the z.mp4 swing has no club
```

> `seed_ready_swing` creates its own session (`location="bay"`). The second test adds an unrelated session and asserts `session=` filters correctly.

Run: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/tests/test_api_swings.py -q` (expect failure).

- [ ] Add a `swing_summary_dict` passthrough to `web/backend/serializers.py` (the repo already returns plain dicts, so this is just an identity/whitelist for clarity — optional; the endpoint can return the repo dicts directly). Keep it simple: the endpoint returns `repo.list_swing_summaries(...)` rows as-is.

- [ ] Add the list route to `web/backend/api_swings.py`. **Place it ABOVE `/latest` and `/{swing_id}`** (empty-path GET on the router prefix `/api/swings`):

```python
@router.get("")
def list_swings(player: int | None = None, session: int | None = None,
                limit: int = 50, conn=Depends(get_conn)):
    return repo.list_swing_summaries(conn, player_id=player,
                                     session_id=session, limit=limit)
```
  - Ensure `Depends`, `get_conn`, `repo` are already imported (they are).

- [ ] Re-run → green.

- [ ] **Wire the Review screen + App:**
  - `lib/types.ts`: add
    ```ts
    export interface SwingSummary {
      id: number; created_at: string; club: string | null; has_shot: boolean;
      hip_sway_in: number | null; shoulder_tilt_deg: number | null;
    }
    ```
  - `lib/api.ts`: add
    ```ts
    export const getSwings = (player?: number, session?: number, limit = 50) => {
      const qs = new URLSearchParams();
      if (player) qs.set("player", String(player));
      if (session) qs.set("session", String(session));
      qs.set("limit", String(limit));
      return getJSON<SwingSummary[]>(`/api/swings?${qs.toString()}`);
    };
    ```
    (extend the `import type { … } from "./types"` to include `SwingSummary`.)
  - `App.tsx`: ReviewScreen currently gets only `swingId={reviewSwingId}`. To let the screen own the picker, pass the resolution inputs too:
    ```tsx
    {activeTab === 'review' && (
      <ReviewScreen
        playerId={activePlayerId}
        sessionId={activeSessionId}
        defaultSwingId={reviewSwingId}
      />
    )}
    ```
  - `pages/ReviewScreen.tsx`: change props to `{ playerId: number | null; sessionId: number | null; defaultSwingId: number | null }`.
    - Add a `selectedId` state, defaulting to `defaultSwingId`:
      ```ts
      const [selectedId, setSelectedId] = useState<number | null>(defaultSwingId)
      useEffect(() => { setSelectedId(defaultSwingId) }, [defaultSwingId])
      ```
    - Fetch the list:
      ```ts
      const { data: swings } = useApi<SwingSummary[]>(
        () => (playerId ? getSwings(playerId, sessionId ?? undefined, 50) : Promise.resolve([])),
        [playerId, sessionId],
      )
      ```
    - `const swingId = selectedId ?? defaultSwingId`. Keep the existing `useApi(() => swingId ? getSwing(swingId) : …, [swingId])` detail fetch (rename its dep to `swingId`).
    - Add a selector at the top of the screen (a native `<select>` styled to match, or a simple list). Minimal dropdown matching the dark theme:
      ```tsx
      {(swings?.length ?? 0) > 0 && (
        <div className="flex items-center gap-3">
          <label className="text-[11px] uppercase tracking-wider text-[#8B978F] font-semibold">Swing</label>
          <select
            value={swingId ?? ''}
            onChange={(e) => setSelectedId(Number(e.target.value))}
            className="bg-[#1A211D] border border-[#242C27] rounded-xl px-4 py-2 text-[#E7EEE9] focus:border-garage-green outline-none min-h-[44px]"
          >
            {(swings ?? []).map((s, i) => (
              <option key={s.id} value={s.id}>
                {`#${s.id} · ${s.club ?? '—'} · ${new Date(s.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}${s.has_shot ? ' · R50' : ''}${i === 0 ? ' (latest)' : ''}`}
              </option>
            ))}
          </select>
        </div>
      )}
      ```
      Place it just inside the screen's root `<div>`, before the HERO block. Keep all existing markup below it. The empty-state and loading/error branches stay; the empty state now also covers "no swings for this player".

### Task 5 — History timeframe filter (client-side)

- [ ] Add a pure `withinTimeframe` helper to `web/frontend/src/lib/format.ts`:

```ts
export type Timeframe = "Session" | "Week" | "Month" | "Year";

// Returns the cutoff Date for a timeframe relative to `now`. "Session" uses a
// 12-hour window (one bay session); Week/Month/Year are calendar-ish spans.
export function timeframeCutoff(tf: Timeframe, now = new Date()): Date {
  const d = new Date(now);
  switch (tf) {
    case "Session": d.setHours(d.getHours() - 12); break;
    case "Week": d.setDate(d.getDate() - 7); break;
    case "Month": d.setMonth(d.getMonth() - 1); break;
    case "Year": d.setFullYear(d.getFullYear() - 1); break;
  }
  return d;
}

export function withinTimeframe<T extends { created_at: string }>(
  points: T[], tf: Timeframe, now = new Date(),
): T[] {
  const cutoff = timeframeCutoff(tf, now).getTime();
  return points.filter((p) => {
    const t = new Date(p.created_at).getTime();
    return Number.isNaN(t) ? true : t >= cutoff;
  });
}
```

- [ ] Edit `web/frontend/src/pages/HistoryScreen.tsx`:
  - Import `withinTimeframe`, and type `timeframe` as `Timeframe` (`const [timeframe, setTimeframe] = useState<Timeframe>('Month')`).
  - Apply the filter to the hero series before mapping to `chartData`:
    ```ts
    const heroPoints = withinTimeframe(hero?.points ?? [], timeframe)
    const chartData = heroPoints.map((p) => ({ date: shortDate(p.created_at), value: p.value }))
    ```
  - Apply the same filter inside the `trends` builder: after fetching each history, `const points = withinTimeframe(histories[i].points ?? [], timeframe)` BEFORE computing `deltaVsBaseline`/sparkline. Add `timeframe` to the `trends` `useApi` deps array so changing the pill recomputes.
  - Remove the `// Phase 3: server-side timeframe filtering; visual-only for now` comment.
  - Empty-state copy: when filtered `chartData.length === 0` but `hero?.points` was non-empty, the existing "No history yet for this player." still renders — acceptable. (Optional nicety: show "No data in this timeframe." when the unfiltered set was non-empty; not required.)

> Why client-side: the seed/history all lands "now" (same-day), so `Month`/`Year` show everything and `Session`/`Week` also include the seeded points (all within 12h of seeding). The verification confirms the pill changes the series without error; it will not visibly thin the seeded data because it is all recent. Note this in the report.

### Task 6 — Frontend unit test for the new pure helper

- [ ] Edit `web/frontend/src/lib/api.test.ts` — add a `withinTimeframe` block (deterministic `now`):

```ts
import { withinTimeframe, timeframeCutoff } from "./format";

describe("withinTimeframe", () => {
  const now = new Date("2026-06-04T12:00:00Z");
  const pts = [
    { created_at: "2026-06-04T06:00:00Z", value: 1 }, // 6h ago
    { created_at: "2026-05-30T12:00:00Z", value: 2 }, // 5d ago
    { created_at: "2026-01-01T12:00:00Z", value: 3 }, // ~5mo ago
  ];
  it("Session keeps only the last 12h", () => {
    expect(withinTimeframe(pts, "Session", now).map(p => p.value)).toEqual([1]);
  });
  it("Week keeps last 7 days", () => {
    expect(withinTimeframe(pts, "Week", now).map(p => p.value)).toEqual([1, 2]);
  });
  it("Year keeps all three", () => {
    expect(withinTimeframe(pts, "Year", now).map(p => p.value)).toEqual([1, 2, 3]);
  });
  it("cutoff is monotonic across spans", () => {
    expect(timeframeCutoff("Session", now).getTime())
      .toBeGreaterThan(timeframeCutoff("Year", now).getTime());
  });
});
```

- [ ] Keep the existing `api.test.ts` cases and `MetricCard.test.tsx` passing (unchanged).

### Task 7 — GATES (build, tests, run-and-verify)

Run from repo root (`C:\Users\chris\Documents\Golf`). Use `& 'C:\Program Files\nodejs\npm.cmd'` if `npm` isn't on PATH.

- [ ] **Backend tests green** (full suite, incl. all Phase 3 additions):
  `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/ store/ -q`
  Expected: all pass. New: `store/tests/test_settings.py` (3), players counts (1), swings summary (1); `web/backend/tests/test_api_settings.py` (4), players counts (1), swings list (2).
- [ ] **Seed runs idempotently** (populates every screen so the run-and-verify has data):
  `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m web.backend.seed_dev` (run twice; swing count stays 3).
- [ ] **Frontend install** (only if deps changed — none expected):
  `& 'C:\Program Files\nodejs\npm.cmd' install --prefix web/frontend`
- [ ] **Build gate (tsc + vite):** `& 'C:\Program Files\nodejs\npm.cmd' run build --prefix web/frontend`
  Expected: `tsc -b` no type errors, `vite build` writes `web/frontend/dist/`. Fix type errors minimally (no global `strict` loosening).
- [ ] **Vitest:** `& 'C:\Program Files\nodejs\npm.cmd' run test --prefix web/frontend`
  Expected: `lib/api.test.ts` (incl. new `withinTimeframe` block) + `MetricCard.test.tsx` pass.
- [ ] **RUN-AND-VERIFY** (real data + the 4 new behaviors):
  1. Start backend (serves built `dist/` at `/` + the API) in background:
     `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m uvicorn web.backend.app:app --port 8000`
  2. Load `http://localhost:8000/` (built dist) OR `& 'C:\Program Files\nodejs\npm.cmd' run dev --prefix web/frontend` and load `http://localhost:5173/`.
  3. Confirm (browser/preview MCP or screenshots):
     - **Connect:** the settings form loads `idle_minutes=15`, `Yards`, `port=921` from `GET /api/settings`. Change Idle to `20`, units to `Meters`, click **Save Settings** → button shows Saved; reload the page → values persist (proves `PUT` + `GET`). Confirm `GET /api/settings` returns the new values (`curl`/devtools).
     - **History:** click each pill (Session/Week/Month/Year) → chart re-renders without error (seeded data all recent, so series stays populated; the point is no crash + the pill drives `withinTimeframe`).
     - **Players:** the "Alex M." card shows a real **Swings** count (the seed makes 3 in the open session + 8 in the history session = 11 total) and a **Sessions** count (2).
     - **Review:** the swing selector lists the player's swings (newest first, latest marked); pick a different swing → the breakdown table + AI read + matched-shot strip update to that swing.
  4. Stop the background uvicorn.
- [ ] **Console clean:** no new console errors from the added selector/save button (note any benign warnings).

### Task 8 — Final verification + report (NO commit)

- [ ] Re-run superpowers:verification-before-completion: confirm EVERY gate command above was actually executed and its output observed (paste the pytest summary line + the vitest summary + the build "built in" line).
- [ ] `git status`: new `web/backend/api_settings.py`, `store/tests/test_settings.py`, `web/backend/tests/test_api_settings.py`; edits to `schema.sql`, `repo.py`, `deps.py`, `capture.py`, `api_capture.py`, `api_players.py`, `api_swings.py`, `serializers.py` (optional), `app.py`, and the frontend `lib/{types,api,format}.ts`, `lib/api.test.ts`, `pages/{Connect,History,Players,Review}Screen.tsx`, `App.tsx`. `node_modules/` + `dist/` NOT staged.
- [ ] Do NOT commit; leave the tree for the orchestrator.
- [ ] Report: confirm the 4 items work end-to-end; list the backend additions + exact shapes; state where the supervisor reads idle/port now (construction in `deps.get_supervisor` + `restart` in `api_capture`); flag anything left as a known limitation (units is stored-only / no live conversion; client-side timeframe filter won't visibly thin same-day seeded data; port change triggers a listener restart).

---

## Notes / Risks

- **Settings table auto-creates.** `init_db` re-runs the full `schema.sql` (`executescript`) on every connect, and the new table uses `CREATE TABLE IF NOT EXISTS`, so no `SCHEMA_VERSION` bump or migration is needed. Existing DBs gain the table on next open.
- **Supervisor reads idle/port in TWO places.** Construction (`deps.get_supervisor`) for a fresh uvicorn boot, and `restart()` (`api_capture.restart` → `sup.apply_settings`) for a live change from the Connect screen. `idle_minutes` takes effect on the next idle sweep; `port` takes effect only when the listener re-spawns (i.e. on restart) — that is why the Connect Save handler should call `restartCapture()` when the port changed. The `client` test fixture builds the supervisor WITHOUT idle/port (defaults), which is correct: `test_restart_applies_settings_*` covers the `restart()` re-read path; constructing-from-settings is exercised implicitly by the real `get_supervisor` (not under test, but trivial).
- **`PUT /api/settings` validation:** reject `units` not in `{yards,meters}` (422), `idle_minutes < 1` (422), `port` outside `1..65535` (422). Unknown keys in the body are ignored by `repo.save_settings` (whitelist on `SETTINGS_DEFAULTS`).
- **`getPlayers` return type changes** from `Player[]` to `PlayerWithCounts[]`. Because `PlayerWithCounts extends Player`, every existing consumer (App's player switcher, Players page) keeps compiling. Verify `tsc` is happy; if any consumer destructured an exact `Player[]`, widen it.
- **Players `lastActive`:** the new counts endpoint does NOT return a timestamp. Decide: keep ONE `getSessions(p.id)` fan-out just for `lastActive`, or set it to `'--'`. Either is acceptable — pick one and note it. (The swing/session COUNTS now come from the API, so the fan-out is no longer needed for those.)
- **`GET /api/swings` route ordering.** The router prefix is `/api/swings`; the empty-path `@router.get("")` must NOT be shadowed by `/{swing_id}`. FastAPI matches the empty path distinctly from `/{swing_id}`, but to be safe declare `list_swings` ("") FIRST, then `/latest`, then `/{swing_id}` (the existing `/latest`-before-`/{swing_id}` order is preserved).
- **Client-side timeframe filter is cosmetic with seeded data.** All seeded swings land "now", so Month/Year (and even Session/Week within 12h/7d) include everything. Verification confirms the pill drives the filter and does not crash; it will not visibly reduce the seeded series. A backend `created_at` range filter is a possible future enhancement but is out of scope (the task says client-side is the simplest).
- **`units` is display-only and stored-only.** Phase 3 stores + reads it; it does NOT re-compute carry/speed across screens. Note this clearly in the report so it is not mistaken for a full units feature.
- **No new npm deps expected.** If any wiring needs one, add to `package.json` and call it out.
- **Swing summary key metrics.** `list_swing_summaries` surfaces `hip_sway_in` + `shoulder_tilt_deg` at impact (the two most-used cards). If a swing has no metrics they come back `null` — the selector label falls back to club/time, which is fine.

---

## Appendix — exact new/changed shapes

- **`Settings`** (GET/PUT `/api/settings`) = `{ idle_minutes: int, units: "yards"|"meters", port: int }`. PUT body is a partial of these; response is the full merged object.
- **`GET /api/players`** row (was `Player`) now = `{ id, name, height_in, handedness, created_at, swing_count: int, session_count: int }`. (`POST /api/players` still returns the bare `Player`.)
- **`GET /api/swings?player=&session=&limit=`** → `SwingSummary[]`, newest first, where **`SwingSummary`** = `{ id, created_at, club: string|null, has_shot: bool, hip_sway_in: number|null, shoulder_tilt_deg: number|null }`.
- **`repo.get_settings(conn)` / `repo.save_settings(conn, dict)`** — global single-row settings, defaults `{idle_minutes:15, units:"yards", port:921}`.
- **`repo.count_swings_for_player` / `repo.count_sessions_for_player`** — `int`.
- **`repo.list_swing_summaries(conn, player_id=None, session_id=None, limit=None)`** — list of the SwingSummary dicts above.
- **`CaptureSupervisor.apply_settings(dict)`** — adopt `idle_minutes` (immediate) + `port` (next spawn).
- **`withinTimeframe(points, tf, now?)` / `timeframeCutoff(tf, now?)`** (frontend `lib/format.ts`) — pure, unit-tested.
