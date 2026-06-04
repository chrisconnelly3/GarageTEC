# Frontend Phase 2 — Wire to Live API + SSE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MagicPatterns' hardcoded demo data in `web/frontend/` with REAL data from the FastAPI backend (`/api/*`) and the SSE live stream (`/events`), across all 7 screens + the Topbar, including the capture controls. After this, running uvicorn + the built/dev frontend shows live R50/pose data; a dev seed (`web/backend/seed_dev.py`) makes every screen populated so the wiring is verifiable without a real R50.

**Methodology:** frontend-pragmatic — concrete code for every change, a **build gate** (`npm run build` = tsc + vite), a **test gate** (vitest + `pytest`), and a **run-and-verify gate** (boot the app, confirm seeded data renders). No per-component TDD; the seed + the run-and-verify step are the substantive verification.

**Tech stack (unchanged from Phase 1):** React 18 · TypeScript (strict, `noUnusedLocals/Parameters: false`) · Vite 5 · Tailwind 3 · framer-motion · lucide-react · recharts · vitest. Backend: FastAPI + sqlite `store/`. Dev proxy already forwards `/api`, `/events`, `/media` → `http://localhost:8000` (`web/frontend/vite.config.ts`).

---

## SCOPE — read before starting

**IN SCOPE (Phase 2):**
- A dev seed script that populates the store idempotently with one demo player, sessions, processed swings (real metric names + contexts + moments + linked shots + coaching), and trend history.
- One small backend addition: `GET /api/swings/latest` (+ a `repo.latest_ready_swing` helper + a test) — the Live screen needs "the newest ready swing for the active player/session" and **no current endpoint returns it**.
- A typed API client `src/lib/api.ts` (TS fns for every endpoint + TS interfaces matching the serializer shapes), and conversion of `useEvents.js` / `useCapture.js` → TS plus generic `useApi` / `useSse` hooks.
- Wiring all 7 screens + Topbar to real fetches + SSE, each with loading / empty / error states. Keep the exact MagicPatterns visual components and their props; only the **data source** changes.
- Investigate + fix the 1 console error seen when the built app loads.

**OUT OF SCOPE:**
- No new visual components, no redesign. Reuse `MetricCard`, `AIInsightCard`, `SwingReplay`, `BallClubStrip`, etc. exactly as shipped (props listed in the appendix).
- Real pose video / skeleton rendering. `SwingReplay` stays a placeholder (it takes only `highlight?`); we wire the data around it but do not build a video player.
- Connect screen **settings persistence** (idle/units/port). Wire the live status indicator; leave the three setting inputs as local-only `useState` with a `// Phase 3: persist via POST /api/capture/settings` note. No settings endpoint exists and adding one is out of scope.
- Any change to capture/pose/metrics/coach pipeline code.

---

## Backend contract (verified against source — the shapes you wire to)

All endpoints are JSON. Serializer shapes are from `web/backend/serializers.py`. Field names below are EXACT.

### Players — `web/backend/api_players.py`
- `GET /api/players` → `Player[]`
- `POST /api/players` body `{name, height_in, handedness}` → `Player`
- **`Player`** = `{ id, name, height_in, handedness, created_at }` (`handedness` is `"R"`|`"L"`)

### Sessions — `web/backend/api_sessions.py`
- `GET /api/sessions?player=<id?>` → `Session[]` (newest first, `ORDER BY id DESC`)
- `GET /api/sessions/{id}` → `{ session: Session, swings: Swing[], coaching: Coaching[] }` (404 if missing)
- **`Session`** = `{ id, player_id, started_at, ended_at, location, notes }`

### Swings — `web/backend/api_swings.py`
- `GET /api/swings/{id}` → `{ swing: Swing, metrics: Metric[], moments: Moment[], shot: Shot|null, coaching: Coaching[], media: Media[] }` (404 if missing)
- **NEW** `GET /api/swings/latest?player=<id>&session=<id?>` → same shape as `GET /api/swings/{id}`, or `204 No Content` when none ready (Task 2).
- **`Swing`** = `{ id, session_id, player_id, created_at, source_video_path, view_layout, fps, width, height, club, notes, shot_id }`
- **`Metric`** = `{ id, swing_id, name, context, value, unit, method, created_at }`
- **`Moment`** = `{ id, swing_id, kind, view, frame_index, time_s }`
- **`Media`** = `{ id, swing_id, kind, path, meta }` (`meta` = parsed JSON or null)
- **`Coaching`** = `{ id, swing_id, session_id, kind, content, model, created_at }` (`content` = parsed JSON; see coach schema below)

### History — `web/backend/api_history.py`
- `GET /api/history?player=<id>&metric=<name>&context=<ctx>` (context default `"overall"`) → `{ player, metric, context, points: [{swing_id, created_at, value}] }`
- ⚠️ **CRITICAL:** metrics are stored with contexts `"address" | "top" | "impact" | "max"` — **never `"overall"`**. The current `getHistory` default of `"overall"` returns ZERO points. The wiring MUST pass a real context (we use `"impact"` for the hero trend). The seed stores `"impact"` history so the chart populates.

### Sync — `web/backend/api_sync.py`
- `GET /api/sync/proposals?session=<id>` → `{ session, proposals: [{swing_id, shot_id, confidence, reason}], unmatched_swings: Swing[], unmatched_shots: Shot[] }`
- `POST /api/sync/apply` body `{swing_id, shot_id}` → `{ok: true}`
- `POST /api/sync/unlink` body `{swing_id}` → `{ok: true}`

### Capture — `web/backend/api_capture.py` (+ `capture.py CaptureStatus`)
- `GET /api/capture/status` → **`CaptureStatus`** = `{ status, paused, connected, shot_count, active_player_id, last_error }` where `status ∈ {"stopped","listening","connected","paused"}`
- `POST /api/capture/pause` → `CaptureStatus`
- `POST /api/capture/resume` → `CaptureStatus`
- `POST /api/capture/restart` → `{ok: true, ...CaptureStatus}`
- `POST /api/capture/active-player` body `{name, height_in, handedness}` → `CaptureStatus` (creates-or-selects the player by name)

### Shot — `web/backend/serializers.py shot_dict`
- **`Shot`** = `{ id, swing_id, player_id, session_id, captured_at, device_id, shot_number, ball_speed, total_spin, spin_axis, hla, vla, carry, club_speed, attack_angle, club_path, face_to_target }` (any numeric may be null)

### SSE — `GET /events` (`web/backend/events.py`)
- `event: swing_ready` data `{swing_id, session_id, player_id}` — fires once per swing that has ≥1 metric AND ≥1 coaching row.
- `event: shot_received` data `{shot_id, player_id, session_id, ball_speed, carry, shot_count}`
- `event: capture_status` data `{status, detail?}` (status e.g. `paused`,`connected`,`listening`,`restarting`)
- `event: active_player_changed` data `{player_id, name}`
- Plus `: keep-alive` comments every ~1.5s. `?once=1` drains and returns (used by a test).

### Media — `GET /media/{path}` serves files under the media root. `mediaUrl(path) => "/media/"+path`.

### The 9 real metric names (from `metrics/defs/*.py`) and their units/contexts
| name | unit | contexts stored | view |
|---|---|---|---|
| `shoulder_tilt_deg` | deg | address, top, impact | face_on |
| `hip_tilt_deg` | deg | address, top, impact | face_on |
| `shoulder_turn_deg` | deg | address, top, impact | face_on |
| `hip_turn_deg` | deg | address, top, impact | face_on |
| `spine_angle_deg` | deg | address, top, impact | down_line |
| `hand_depth_in` | in | address, top, impact | down_line |
| `early_extension_in` | in | impact, max | down_line |
| `hip_sway_in` | in | top, impact, max | face_on |
| `head_sway_in` | in | top, impact, max | face_on |

`method` is e.g. `"exact"` or `"foreshortening_2d;confidence=low"` (a `;confidence=low` substring → the `~est.` badge on `MetricCard`).

### AI coach `content` schema (from `coach/prompt.py OUTPUT_SCHEMA`) — the JSON stored in `coaching.content`
```jsonc
{
  "headline": "string",
  "findings": [
    { "metric": "hip_sway_in", "context": "impact", "value": 2.5, "unit": "in",
      "vs_baseline": "string|null", "vs_ideal": "string|null",
      "ball_effect": "string|null", "severity": "good|neutral|bad|null" }
  ],
  "drills": [ { "name": "string", "why": "string|null", "how": "string|null" } ],
  "confidence_notes": ["string"]
}
```
The seed and all `AIInsightCard` wiring use THIS exact shape.

---

## Mapping: which screen needs which endpoint(s)

| Screen / area | Real data source | Empty/loading/error |
|---|---|---|
| **Topbar** | `GET /api/players` (switcher), `GET /api/capture/status` + SSE `capture_status`/`active_player_changed` (status pill), `POST /api/capture/active-player`, `POST /api/capture/pause|resume` | status null → skeleton pill; no players → just controls |
| **Live** | `GET /api/swings/latest?player&session` (NEW) on mount + on SSE `swing_ready`/`shot_received`; baseline via `GET /api/history?metric&context=impact`; coaching from the swing payload; ball/club from `swing.shot` | no ready swing → MP "Waiting for your R50" empty state |
| **Review** | `GET /api/swings/{id}` (id from a swing picker / latest) | no swing selected → prompt; 404 → error |
| **History** | `GET /api/history?player&metric&context=impact` (hero + each trend card) | no points → "no history yet" |
| **Sessions** | `GET /api/sessions` (+ `GET /api/sessions/{id}` for swing count/coaching summary, lazy) | `[]` → empty state |
| **Players** | `GET /api/players`; add via `POST /api/players`; "Set as Active" → `POST /api/capture/active-player` | `[]` → just the Add card |
| **Sync** | `GET /api/sync/proposals?session`; `POST /api/sync/apply`; `POST /api/sync/unlink` | no proposals/unmatched → "all matched" |
| **Connect** | `GET /api/capture/status` + SSE for the live indicator; settings inputs stay local (note) | — |

**Active player/session resolution (shared):** the backend's source of truth for "who's hitting" is `capture/status.active_player_id`. For session, derive the active player's open session via `GET /api/sessions?player=<active_player_id>` and take the first (newest). Hold `{activePlayerId, activeSessionId}` in `App.tsx` and pass down (or via a tiny context). The seed leaves the demo player as the active player and its session open so this resolves on first load.

---

## File plan

```
web/backend/
  seed_dev.py                 # NEW (Task 1) — idempotent demo seed + __main__
  api_swings.py               # EDIT (Task 2) — add GET /api/swings/latest
  tests/test_api_swings.py    # EDIT (Task 2) — test the new endpoint
store/
  repo.py                     # EDIT (Task 2) — add latest_ready_swing()
  tests/test_swings.py        # EDIT (Task 2) — test the helper
web/frontend/src/
  lib/
    api.ts                    # NEW (Task 3) — typed client, replaces src/api.js usage
    types.ts                  # NEW (Task 3) — TS interfaces for all shapes
    useApi.ts                 # NEW (Task 3) — generic fetch hook {data,loading,error,reload}
    useSse.ts                 # NEW (Task 3) — typed SSE subscription
    format.ts                 # NEW (Task 3) — label maps + metric→display helpers
  useEvents.ts                # CONVERT from useEvents.js (Task 3)
  useCapture.ts               # CONVERT from useCapture.js (Task 3)
  api.js                      # DELETE (Task 3) — superseded by lib/api.ts
  App.tsx                     # EDIT (Task 4) — own active player/session + SSE, pass down
  components/Topbar.tsx       # EDIT (Task 4)
  pages/LiveScreen.tsx        # EDIT (Task 5)
  pages/ReviewScreen.tsx      # EDIT (Task 6)
  pages/HistoryScreen.tsx     # EDIT (Task 7)
  pages/SessionsScreen.tsx    # EDIT (Task 8)
  pages/PlayersScreen.tsx     # EDIT (Task 8)
  pages/SyncScreen.tsx        # EDIT (Task 9)
  pages/ConnectScreen.tsx     # EDIT (Task 9)
  lib/api.test.ts             # NEW (Task 10) — vitest unit for buildHistoryUrl/formatters
```
`node_modules/` and `dist/` stay gitignored (already in `web/frontend/.gitignore`). Never stage them.

---

## Tasks

### Task 1 — Dev seed script (`web/backend/seed_dev.py`)

Idempotent: re-running must NOT duplicate. Strategy: `get_or_create_player` by name; for the session, reuse the player's open session if present else create one; for swings, only add if the player has fewer than the target count (keyed off `len(repo.list_swings(conn, session_id))`). Use the REAL metric names/contexts/units and the REAL coach `content` schema.

- [ ] Create `web/backend/seed_dev.py`:

```python
"""Idempotent dev seed: a demo player with processed swings so every Screen
renders real data without a live R50. Run:

    & 'C:\\Users\\chris\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' -m web.backend.seed_dev
"""
import json
import random

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Media, Coaching

PLAYER = {"name": "Alex M.", "height_in": 72.0, "handedness": "R"}
TARGET_SWINGS = 3          # swings in the open/live session
HISTORY_SWINGS = 8         # extra older swings for trend charts
CONTEXTS = ("address", "top", "impact")

# (name, unit, method, baseline_value_at_impact, per-swing jitter)
METRIC_SPEC = [
    ("shoulder_tilt_deg", "deg", "exact", 38.0, 3.0),
    ("hip_tilt_deg", "deg", "exact", 12.0, 2.0),
    ("shoulder_turn_deg", "deg", "exact", 95.0, 5.0),
    ("hip_turn_deg", "deg", "exact", 48.0, 4.0),
    ("spine_angle_deg", "foreshortening_2d;confidence=low", "foreshortening_2d", 42.0, 2.0),
    ("hand_depth_in", "in", "exact", 14.0, 1.5),
    ("early_extension_in", "in", "exact", 1.8, 0.6),
    ("hip_sway_in", "in", "ratio", 2.5, 0.8),
    ("head_sway_in", "in", "ratio", 1.1, 0.5),
]


def _coaching_content():
    return {
        "headline": "Good power, but sliding hips are causing inconsistency.",
        "findings": [
            {"metric": "hip_sway_in", "context": "impact", "value": 2.5,
             "unit": "in", "vs_baseline": "+0.4 in vs your recent average",
             "vs_ideal": "above the 0-2 in ideal range",
             "ball_effect": "tends to push starts right",
             "severity": "bad"},
            {"metric": "shoulder_turn_deg", "context": "top", "value": 95.0,
             "unit": "deg", "vs_baseline": "+5 deg vs baseline",
             "vs_ideal": "inside the 90-110 deg ideal range",
             "ball_effect": "added ~3 mph club speed", "severity": "good"},
        ],
        "drills": [
            {"name": "Chair Drill", "why": "Stops the lead hip sliding past the ball",
             "how": "Set a chair against your lead hip; turn into it without touching."},
            {"name": "Pause at Top", "why": "Improves transition sequencing",
             "how": "Swing to the top, hold one beat, then start down from the ground up."},
        ],
        "confidence_notes": ["spine_angle_deg is foreshortening-estimated (low confidence)."],
    }


def _add_processed_swing(conn, session_id, player_id, *, club, jitter, with_shot,
                         with_coaching):
    sw = repo.add_swing(conn, session_id, player_id, "swings/seed/source.mp4",
                        view_layout="face_on", fps=240.0, width=1920,
                        height=1080, club=club)
    repo.save_moments(conn, sw.id, [
        Moment(sw.id, "address", "face_on", 0, 0.0),
        Moment(sw.id, "top", "face_on", 80, 0.33),
        Moment(sw.id, "impact", "face_on", 120, 0.50),
    ])
    metrics = []
    for name, unit, method, base, spread in METRIC_SPEC:
        for ctx in CONTEXTS:
            # vary by context so address<top<impact reads sensibly for the table
            scale = {"address": 0.25, "top": 0.7, "impact": 1.0}[ctx]
            val = round(base * scale + jitter * spread, 1)
            metrics.append(Metric(sw.id, name, ctx, val, unit, method))
    repo.save_metrics(conn, sw.id, metrics)
    repo.save_media(conn, Media(sw.id, "annotated_video", "swings/seed/annotated.mp4"))
    if with_shot:
        shot = repo.save_shot(conn, Shot(
            captured_at=dbmod.now_iso(), player_id=player_id, session_id=session_id,
            ball_speed=round(160 + jitter * 6, 1), total_spin=2450, spin_axis=-1.2,
            hla=0.8, vla=round(12.0 + jitter, 1), carry=round(280 + jitter * 8, 1),
            club_speed=round(110 + jitter * 3, 1), attack_angle=2.4, club_path=2.1,
            face_to_target=1.5))
        repo.link_shot_to_swing(conn, shot.id, sw.id)
    if with_coaching:
        repo.save_coaching(conn, Coaching(
            swing_id=sw.id, session_id=None, kind="swing",
            content_json=json.dumps(_coaching_content()), model="claude-seed"))
    return sw


def seed(conn):
    player = repo.get_or_create_player(conn, **PLAYER)

    # ---- history session (older, closed) for trend charts ----------------
    if not any(s.location == "seed-history"
               for s in repo.list_sessions(conn, player_id=player.id)):
        hist = repo.create_session(conn, player.id, location="seed-history")
        for i in range(HISTORY_SWINGS):
            # decreasing hip_sway over time -> visible downward trend
            _add_processed_swing(conn, hist.id, player.id, club="Driver",
                                 jitter=(HISTORY_SWINGS - i) * 0.15,
                                 with_shot=True, with_coaching=(i == HISTORY_SWINGS - 1))
        repo.end_session(conn, hist.id)

    # ---- live/open session for the Live + Sync screens -------------------
    open_sess = repo.get_open_session(conn, player.id)
    if open_sess is None:
        open_sess = repo.create_session(conn, player.id, location="seed-bay")
    existing = repo.list_swings(conn, session_id=open_sess.id)
    for i in range(max(0, TARGET_SWINGS - len(existing))):
        _add_processed_swing(conn, open_sess.id, player.id, club="7i",
                             jitter=random.uniform(-0.5, 0.5),
                             with_shot=(i < TARGET_SWINGS - 1),  # leave 1 unmatched for Sync
                             with_coaching=True)

    print(f"Seeded player={player.id} open_session={open_sess.id} "
          f"swings={len(repo.list_swings(conn, session_id=open_sess.id))}")
    return player


def main():
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    try:
        seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
```

- [ ] Run it once and confirm output:
  `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m web.backend.seed_dev`
  Expected: prints `Seeded player=... open_session=... swings=3`. Run a second time → swing count stays 3 (idempotent).

> Why one swing is left unmatched: the Sync screen needs an unmatched swing (and/or proposals) to show. Leaving the last live swing without a linked shot, plus the matched ones, gives Sync real rows.

### Task 2 — Backend addition: `GET /api/swings/latest` (+ repo helper + tests)

The Live screen needs the newest READY swing (≥1 metric AND ≥1 coaching) for the active player, optionally scoped to a session. No endpoint returns this today.

- [ ] Add to `store/repo.py` (near `get_swing`):

```python
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
```

- [ ] Add to `web/backend/api_swings.py` (a `latest` route — declare it BEFORE `/{swing_id}` so `latest` is not captured as an id):

```python
from fastapi import Response

@router.get("/latest")
def latest_swing(player: int, session: int | None = None,
                 conn=Depends(get_conn)):
    swing = repo.latest_ready_swing(conn, player, session_id=session)
    if swing is None:
        return Response(status_code=204)
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    return {
        "swing": swing_dict(swing),
        "metrics": [metric_dict(m) for m in repo.get_metrics(conn, swing.id)],
        "moments": [moment_dict(m) for m in repo.get_moments(conn, swing.id)],
        "shot": shot_dict(shot),
        "coaching": [coaching_dict(c)
                     for c in repo.get_coaching(conn, swing_id=swing.id)],
        "media": [media_dict(md) for md in repo.get_media(conn, swing.id)],
    }
```

> Route ordering: FastAPI matches in declaration order. Put `@router.get("/latest")` ABOVE the existing `@router.get("/{swing_id}")`, otherwise `/latest` hits the `{swing_id}` route and 422s on int parse. The implementer must move/insert accordingly.

- [ ] Add a store test to `store/tests/test_swings.py`:

```python
def test_latest_ready_swing_picks_newest_with_metric_and_coaching(conn):
    import json
    from store.models import Metric, Coaching
    p = repo.get_or_create_player(conn, "L", 70.0, "R")
    sid = repo.create_session(conn, p.id).id
    bare = repo.add_swing(conn, sid, p.id, "a.mp4")          # no metric/coaching
    ready = repo.add_swing(conn, sid, p.id, "b.mp4")
    repo.save_metrics(conn, ready.id, [Metric(ready.id, "hip_sway_in", "impact", 2.5, "in", "ratio")])
    repo.save_coaching(conn, Coaching(swing_id=ready.id, session_id=None, kind="swing",
                                      content_json=json.dumps({"headline": "x"}), model="m"))
    got = repo.latest_ready_swing(conn, p.id)
    assert got is not None and got.id == ready.id
    assert repo.latest_ready_swing(conn, p.id, session_id=sid + 99) is None
```

- [ ] Add an API test to `web/backend/tests/test_api_swings.py`:

```python
def test_latest_swing_endpoint(client, conn):
    p = seed_player(conn)
    swing = seed_ready_swing(conn, p)
    r = client.get(f"/api/swings/latest?player={p.id}")
    assert r.status_code == 200
    assert r.json()["swing"]["id"] == swing.id

def test_latest_swing_204_when_none(client, conn):
    p = seed_player(conn)
    r = client.get(f"/api/swings/latest?player={p.id}")
    assert r.status_code == 204
```

(`seed_player`/`seed_ready_swing` already exist in `web/backend/tests/conftest.py`.)

### Task 3 — Typed API client, types, generic hooks, formatters

- [ ] Create `web/frontend/src/lib/types.ts` (interfaces mirror the serializers EXACTLY):

```ts
export type Handedness = "R" | "L";
export type CaptureState = "stopped" | "listening" | "connected" | "paused";

export interface Player { id: number; name: string; height_in: number; handedness: Handedness; created_at: string; }
export interface Session { id: number; player_id: number; started_at: string; ended_at: string | null; location: string | null; notes: string | null; }
export interface Swing { id: number; session_id: number; player_id: number; created_at: string; source_video_path: string | null; view_layout: string | null; fps: number | null; width: number | null; height: number | null; club: string | null; notes: string | null; shot_id: number | null; }
export interface Metric { id: number; swing_id: number; name: string; context: string | null; value: number | null; unit: string | null; method: string | null; created_at: string; }
export interface Moment { id: number; swing_id: number; kind: string; view: string | null; frame_index: number | null; time_s: number | null; }
export interface Media { id: number; swing_id: number; kind: string; path: string; meta: unknown | null; }
export interface Shot { id: number; swing_id: number | null; player_id: number | null; session_id: number | null; captured_at: string; device_id: string | null; shot_number: number | null; ball_speed: number | null; total_spin: number | null; spin_axis: number | null; hla: number | null; vla: number | null; carry: number | null; club_speed: number | null; attack_angle: number | null; club_path: number | null; face_to_target: number | null; }

export interface CoachFinding { metric: string; context?: string | null; value: number; unit?: string | null; vs_baseline?: string | null; vs_ideal?: string | null; ball_effect?: string | null; severity?: "good" | "neutral" | "bad" | null; }
export interface CoachDrill { name: string; why?: string | null; how?: string | null; }
export interface CoachContent { headline: string; findings: CoachFinding[]; drills: CoachDrill[]; confidence_notes?: string[]; }
export interface Coaching { id: number; swing_id: number | null; session_id: number | null; kind: string; content: CoachContent | null; model: string | null; created_at: string; }

export interface SwingDetail { swing: Swing; metrics: Metric[]; moments: Moment[]; shot: Shot | null; coaching: Coaching[]; media: Media[]; }
export interface SessionDetail { session: Session; swings: Swing[]; coaching: Coaching[]; }
export interface CaptureStatus { status: CaptureState; paused: boolean; connected: boolean; shot_count: number; active_player_id: number | null; last_error: string | null; }
export interface HistoryPoint { swing_id: number; created_at: string; value: number; }
export interface History { player: number; metric: string; context: string; points: HistoryPoint[]; }
export interface SyncProposal { swing_id: number; shot_id: number; confidence: number; reason: string; }
export interface SyncProposals { session: number; proposals: SyncProposal[]; unmatched_swings: Swing[]; unmatched_shots: Shot[]; }
export interface ActivePlayerIn { name: string; height_in: number; handedness: Handedness; }
```

- [ ] Create `web/frontend/src/lib/api.ts` (typed fns for EVERY endpoint; `getJSON` treats 204 as `null`):

```ts
import type {
  Player, Session, SwingDetail, SessionDetail, History, SyncProposals,
  CaptureStatus, ActivePlayerIn,
} from "./types";

async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  if (r.status === 204) return null as T;
  return r.json() as Promise<T>;
}
async function postJSON<T>(url: string, body: unknown): Promise<T> {
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${url}`);
  return r.json() as Promise<T>;
}

export const getPlayers = () => getJSON<Player[]>("/api/players");
export const createPlayer = (p: ActivePlayerIn) => postJSON<Player>("/api/players", p);

export const getSessions = (player?: number) =>
  getJSON<Session[]>("/api/sessions" + (player ? `?player=${player}` : ""));
export const getSession = (id: number) => getJSON<SessionDetail>(`/api/sessions/${id}`);

export const getSwing = (id: number) => getJSON<SwingDetail>(`/api/swings/${id}`);
export const getLatestSwing = (player: number, session?: number) =>
  getJSON<SwingDetail | null>(
    `/api/swings/latest?player=${player}` + (session ? `&session=${session}` : ""));

export const buildHistoryUrl = (player: number, metric: string, context = "impact") =>
  `/api/history?player=${player}&metric=${encodeURIComponent(metric)}&context=${encodeURIComponent(context)}`;
export const getHistory = (player: number, metric: string, context = "impact") =>
  getJSON<History>(buildHistoryUrl(player, metric, context));

export const getProposals = (session: number) =>
  getJSON<SyncProposals>(`/api/sync/proposals?session=${session}`);
export const applyMatch = (swing_id: number, shot_id: number) =>
  postJSON<{ ok: true }>("/api/sync/apply", { swing_id, shot_id });
export const unlinkSwing = (swing_id: number) =>
  postJSON<{ ok: true }>("/api/sync/unlink", { swing_id });

export const mediaUrl = (path: string) => `/media/${path}`;

export const getCaptureStatus = () => getJSON<CaptureStatus>("/api/capture/status");
export const pauseCapture = () => postJSON<CaptureStatus>("/api/capture/pause", {});
export const resumeCapture = () => postJSON<CaptureStatus>("/api/capture/resume", {});
export const restartCapture = () => postJSON<CaptureStatus & { ok: true }>("/api/capture/restart", {});
export const setActivePlayer = (p: ActivePlayerIn) =>
  postJSON<CaptureStatus>("/api/capture/active-player", p);
```

> Note the default `context` is `"impact"`, NOT `"overall"` — see the History CRITICAL note. `getLatestSwing` returns `null` on 204.

- [ ] Create `web/frontend/src/lib/format.ts` (display helpers; pure, unit-tested in Task 10):

```ts
export const METRIC_LABEL: Record<string, string> = {
  shoulder_tilt_deg: "Shoulder Tilt", hip_tilt_deg: "Hip Tilt",
  shoulder_turn_deg: "Shoulder Turn", hip_turn_deg: "Hip Turn",
  spine_angle_deg: "Spine Angle", hand_depth_in: "Hand Depth",
  early_extension_in: "Early Ext.", hip_sway_in: "Hip Sway",
  head_sway_in: "Head Sway",
};
// (min,max) ideal ranges used by MetricCard.idealRange
export const METRIC_IDEAL: Record<string, [number, number]> = {
  shoulder_tilt_deg: [35, 45], hip_tilt_deg: [8, 16], shoulder_turn_deg: [90, 110],
  hip_turn_deg: [40, 55], spine_angle_deg: [40, 45], hand_depth_in: [12, 16],
  early_extension_in: [0, 1], hip_sway_in: [0, 2], head_sway_in: [0, 1.5],
};
// which direction is "good" for MetricCard.deltaGood
export const METRIC_GOOD: Record<string, "up" | "down" | "neutral"> = {
  shoulder_tilt_deg: "up", hip_tilt_deg: "neutral", shoulder_turn_deg: "up",
  hip_turn_deg: "up", spine_angle_deg: "neutral", hand_depth_in: "up",
  early_extension_in: "down", hip_sway_in: "down", head_sway_in: "down",
};
export const labelFor = (name: string) => METRIC_LABEL[name] ?? name;
export const isEstimated = (method?: string | null) =>
  !!method && method.includes("confidence=low");
export const heightToFtIn = (inches: number) =>
  `${Math.floor(inches / 12)}' ${Math.round(inches % 12)}"`;
// baseline = mean of all but the latest history point; delta = latest - baseline
export function deltaVsBaseline(points: { value: number }[]): { value: number; delta: number } {
  if (points.length === 0) return { value: 0, delta: 0 };
  const latest = points[points.length - 1].value;
  const prior = points.slice(0, -1);
  if (prior.length === 0) return { value: latest, delta: 0 };
  const base = prior.reduce((s, p) => s + p.value, 0) / prior.length;
  return { value: latest, delta: Math.round((latest - base) * 10) / 10 };
}
```

- [ ] Create `web/frontend/src/lib/useApi.ts` (generic data hook):

```ts
import { useCallback, useEffect, useState } from "react";

export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback(() => {
    let alive = true;
    setLoading(true); setError(null);
    fn().then((d) => { if (alive) { setData(d); setLoading(false); } })
        .catch((e) => { if (alive) { setError(String(e)); setLoading(false); } });
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => load(), [load]);
  return { data, loading, error, reload: load };
}
```

- [ ] Create `web/frontend/src/lib/useSse.ts` (typed wrapper around the existing `/events` stream — generalizes `useEvents`):

```ts
import { useEffect, useRef } from "react";

type Handlers = Record<string, (data: any) => void>;

export function useSse(handlers: Handlers) {
  const ref = useRef(handlers);
  ref.current = handlers;
  useEffect(() => {
    const es = new EventSource("/events");
    const names = ["swing_ready", "shot_received", "capture_status", "active_player_changed"];
    const listeners = names.map((name) => {
      const fn = (e: MessageEvent) => {
        try { ref.current[name]?.(JSON.parse(e.data)); } catch { /* ignore */ }
      };
      es.addEventListener(name, fn as EventListener);
      return [name, fn] as const;
    });
    return () => { listeners.forEach(([n, fn]) => es.removeEventListener(n, fn as EventListener)); es.close(); };
  }, []);
}
```

- [ ] Convert `web/frontend/src/useEvents.js` → `web/frontend/src/useEvents.ts` (typed; keep the `{lastSwing,lastCapture}` API so any existing import still works), and `useCapture.js` → `useCapture.ts` importing from `./lib/api`:

```ts
// useEvents.ts
import { useState } from "react";
import { useSse } from "./lib/useSse";
import type { Swing } from "./lib/types";

type SwingReady = { swing_id: number; session_id: number; player_id: number };
type CaptureEvt = { type: string; data: any };

export default function useEvents() {
  const [lastSwing, setLastSwing] = useState<SwingReady | null>(null);
  const [lastCapture, setLastCapture] = useState<CaptureEvt | null>(null);
  useSse({
    swing_ready: (d) => setLastSwing(d),
    shot_received: (d) => setLastCapture({ type: "shot_received", data: d }),
    capture_status: (d) => setLastCapture({ type: "capture_status", data: d }),
    active_player_changed: (d) => setLastCapture({ type: "active_player_changed", data: d }),
  });
  return { lastSwing, lastCapture };
}
```
```ts
// useCapture.ts
import { useEffect, useState } from "react";
import { getCaptureStatus, pauseCapture, resumeCapture, restartCapture, setActivePlayer } from "./lib/api";
import type { CaptureStatus, ActivePlayerIn } from "./lib/types";

export default function useCapture(lastCapture: unknown) {
  const [status, setStatus] = useState<CaptureStatus | null>(null);
  const refresh = () => getCaptureStatus().then(setStatus).catch(() => {});
  useEffect(() => { refresh(); }, []);
  useEffect(() => { if (lastCapture) refresh(); }, [lastCapture]);
  return {
    status,
    pause: () => pauseCapture().then(setStatus),
    resume: () => resumeCapture().then(setStatus),
    restart: () => restartCapture().then(refresh),
    selectPlayer: (p: ActivePlayerIn) => setActivePlayer(p).then(setStatus),
    refresh,
  };
}
```

- [ ] **Delete `web/frontend/src/api.js`** (superseded by `lib/api.ts`). Grep for any remaining `from "./api"` / `from "../api"` imports and repoint them to `./lib/api` / `../lib/api`. (`useCapture` was the only importer; it now imports `./lib/api`.)

### Task 4 — `App.tsx` owns active player/session + SSE; wire Topbar

`App.tsx` becomes the single owner of: capture status (via `useCapture`+`useEvents`), the player list, and the resolved `{activePlayerId, activeSessionId}`. It passes real props to `Topbar` and provides player/session ids to the screens (props drilling is fine for 7 screens; a small React context is optional).

- [ ] Edit `web/frontend/src/App.tsx`:
  - Import `useEvents`, `useCapture`, `getPlayers`, `getSessions`.
  - `const { lastSwing, lastCapture } = useEvents();`
  - `const capture = useCapture(lastCapture);`
  - Load players with `useApi(getPlayers, [])`; the active player id is `capture.status?.active_player_id`.
  - Derive `activeSessionId`: when `active_player_id` changes, `getSessions(active_player_id)` and take `[0]?.id` (newest). Store in state.
  - Map `capture.status.status` → Topbar's `r50Status` union: `connected→'connected'`, `paused→'paused'`, anything else (`listening`/`stopped`)→`'waiting'`. Derive `isPaused` from `capture.status?.paused`.
  - Pass to `Topbar`: `players`, `activePlayerId`, `r50Status`, `isPaused`, `onPause/onResume` (call `capture.pause/resume`), `onSelectPlayer` (call `capture.selectPlayer({name,height_in,handedness})`).
  - Pass `activePlayerId`, `activeSessionId`, and `lastSwing`/`lastCapture` (or the whole `capture`) down to the screens that need them (Live, History, Sync, Players, Connect).
  - Remove the demo `useEffect` that fakes `r50Status` from `isPaused`.

- [ ] Edit `web/frontend/src/components/Topbar.tsx` — replace the hardcoded `players` array and the local pause logic with props. New props interface:

```ts
interface TopbarPlayer { id: number; name: string; }
interface TopbarProps {
  players: TopbarPlayer[];
  activePlayerId: number | null;
  isPaused: boolean;
  r50Status: "connected" | "waiting" | "paused";
  onPause: () => void;
  onResume: () => void;
  onSelectPlayer: (p: TopbarPlayer) => void;
}
```
  - Render `players.map(...)`; `player.active = player.id === activePlayerId`.
  - Drop the `avatar` image source (pravatar URLs are demo); use `AvatarFallback` with `player.name.charAt(0)` only (avoids an external network image — and is part of the console-error fix in Task 11).
  - The Pause/Resume button calls `isPaused ? onResume() : onPause()`.
  - Keep all class names / visual structure identical.

> `onSelectPlayer` must pass `{name, height_in, handedness}` to `setActivePlayer`. Topbar only has `{id,name}`, so App should pass a richer `onSelectPlayer` that looks up the full `Player` (height/handedness) from its players list before calling `capture.selectPlayer`. Implement the lookup in `App.tsx`; Topbar just calls `onSelectPlayer({id,name})`.

### Task 5 — Live screen

Goal: real latest ready swing + baseline deltas + coaching + ball/club; SSE-refresh; MP "Waiting" empty state when none.

- [ ] Edit `web/frontend/src/pages/LiveScreen.tsx`. Props: `{ playerId: number | null, sessionId: number | null, lastSwing, lastCapture }`.
  - Remove the demo `setInterval` toggle and the hardcoded `metrics`/`insights`.
  - Fetch: `const { data, loading, error, reload } = useApi(() => playerId ? getLatestSwing(playerId, sessionId ?? undefined) : Promise.resolve(null), [playerId, sessionId]);`
  - Re-fetch on SSE: `useEffect(() => { reload(); }, [lastSwing]);` (a new `swing_ready` → reload).
  - `status = data ? 'captured' : 'waiting'`. Keep MP's `AnimatePresence` waiting block VERBATIM for the empty state; show it when `!data` (and a spinner/skeleton while `loading`, an error banner on `error`).
  - Build the 6 metric cards from `data.metrics` filtered to `context==="impact"`, for these names in order: `shoulder_tilt_deg, hip_sway_in, spine_angle_deg, early_extension_in, hand_depth_in, shoulder_turn_deg`. For each, fetch that metric's history (`getHistory(playerId, name, "impact")`) to compute `delta`/baseline via `deltaVsBaseline`. To avoid 6 parallel history calls per render, fetch them once with `Promise.all` in a `useApi` keyed on `data.swing.id`. MetricCard props:
    ```ts
    <MetricCard name={labelFor(m.name)} value={m.value!} unit={m.unit ?? ""}
      delta={delta} deltaGood={METRIC_GOOD[m.name]} idealRange={METRIC_IDEAL[m.name]}
      currentNum={m.value!} isEstimated={isEstimated(m.method)} highlight={m.name==="hip_sway_in"} />
    ```
  - AIInsightCard: `headline = data.coaching[0]?.content?.headline`; map `content.findings` → `Insight[]`:
    ```ts
    insights = findings.map((f, i) => ({
      id: String(i),
      type: f.severity === "good" ? "power" : f.severity === "bad" ? "mechanic" : "timing",
      text: f.vs_baseline || f.vs_ideal || f.ball_effect || `${labelFor(f.metric)} ${f.value}${f.unit ?? ""}`,
      metric: labelFor(f.metric),
      drill: data.coaching[0]?.content?.drills[i]?.name ?? "Maintain",
      severity: (f.severity as "good"|"neutral"|"bad") ?? "neutral",
    }))
    ```
  - `SwingReplay` stays `<SwingReplay highlight />` (placeholder — no video wiring).
  - `BallClubStrip` (Task 5b) now takes a `shot` prop (see below) built from `data.shot`.

- [ ] **Task 5b — make `BallClubStrip` data-driven.** It currently hardcodes 8 stats. Add an optional `shot?: Shot | null` prop; when provided, map fields → the 8 labels; when absent, render em-dashes. Keep the exact markup/labels:
  ```ts
  // mapping: Ball Speed=ball_speed mph, Spin=total_spin rpm, Launch=vla deg,
  // Carry=carry yds, Club Speed=club_speed mph, Path=club_path In-Out,
  // Face=face_to_target Open, AoA=attack_angle deg (prefix + if >0)
  ```
  Default `shot` to `null` so Review/other callers without data still compile. Format nulls as `"--"`.

### Task 6 — Review screen

- [ ] Edit `web/frontend/src/pages/ReviewScreen.tsx`. Props: `{ swingId: number | null }` (App passes the latest swing id, or a session's first swing; a full swing picker is Phase 3 — for now default to the latest ready swing id resolved in App).
  - `const { data, loading, error } = useApi(() => swingId ? getSwing(swingId) : Promise.resolve(null), [swingId]);`
  - Empty state when `!swingId`/`!data`: a centered "Select a swing to review" card. Loading spinner; error banner.
  - The "Body Mechanics Breakdown" table rows come from `data.metrics`: group by `name`, columns = value at `context` `address`/`top`/`impact`. Build a row per the 9 metric names that have data:
    ```ts
    const byName = groupBy(data.metrics, m => m.name);
    rows = Object.entries(byName).map(([name, ms]) => ({
      name: labelFor(name),
      address: fmt(ms.find(x=>x.context==="address")),
      top: fmt(ms.find(x=>x.context==="top")),
      impact: fmt(ms.find(x=>x.context==="impact")),
      status: statusFor(name, ms.find(x=>x.context==="impact")?.value),  // good/bad/neutral vs ideal
    }))
    ```
    `fmt(metric)` → `"38°"`/`"2.5\""` using the unit; missing → `"--"`. `statusFor` compares the impact value to `METRIC_IDEAL[name]` (in-range=good, out=bad, no-ideal=neutral).
  - The 8-phase timeline can keep its static phase labels for now (only Address/Top/Impact have data); highlight the phases that exist in `data.moments` (kinds `address`/`top`/`impact`). Clicking is cosmetic.
  - `AIInsightCard` headline + insights from `data.coaching[0].content` (same mapping as Live).
  - `BallClubStrip shot={data.shot}` (Task 5b prop).

### Task 7 — History screen

- [ ] Edit `web/frontend/src/pages/HistoryScreen.tsx`. Props: `{ playerId: number | null }`.
  - Hero chart: `getHistory(playerId, heroMetric, "impact")` where `heroMetric` defaults to `shoulder_tilt_deg`. Map `points` → recharts data `[{date: shortDate(created_at), value}]`. Keep the existing `<LineChart>` markup; swap `chartData` for the fetched series. Title = `${labelFor(heroMetric)}`.
  - Trend cards: for 4 metrics (`shoulder_tilt_deg, hip_sway_in, spine_angle_deg, shoulder_turn_deg`), fetch each history (one `useApi` doing `Promise.all`), compute `{value, delta}` via `deltaVsBaseline`, build `sparkline = points.map(p=>p.value).slice(-5)`. `deltaGood = METRIC_GOOD[name]`. `isPB` = latest is the min (for down-good) or max (for up-good) of the series. Keep the existing card markup.
  - The metric filter chips / timeframe toggle can stay visual-only for now (note: server-side timeframe filtering is Phase 3 — history returns all points). Loading/empty: "No history yet for this player."

### Task 8 — Sessions + Players screens

- [ ] Edit `web/frontend/src/pages/SessionsScreen.tsx`. Props: `{ activeSessionId: number | null }`.
  - `const { data: sessions, loading, error } = useApi(getSessions, []);`
  - For each `Session`, render a card: `isLive = ended_at === null` (or `id === activeSessionId`); `date = formatDateTime(started_at)`; `player` name needs a player lookup — fetch players once and map `player_id→name` (pass players from App, or `useApi(getPlayers)` here). Swing count + clubs + AI summary require `getSession(id)` — fetch lazily/once per visible card via `Promise.all` over the session ids (cap to first ~10). Map: `swings = detail.swings.length`, `clubs = unique(detail.swings.map(s=>s.club)).join(", ")`, `summary = detail.coaching[0]?.content?.headline ?? "No summary yet."`, `stats = []` (or derive an avg from a metric — optional).
  - Empty: "No sessions yet." Keep card markup; drop pravatar avatar images (fallback initials only).

- [ ] Edit `web/frontend/src/pages/PlayersScreen.tsx`. Props: `{ activePlayerId: number | null, onSetActive: (p: Player) => void, onAdded: () => void }`.
  - `const { data: players, loading, reload } = useApi(getPlayers, []);`
  - Map each `Player` → card: `height = heightToFtIn(height_in)`, `handedness`, `isActive = id === activePlayerId`. `swings`/`sessions`/`lastActive` are not directly available — show `sessions` via `getSessions(player.id).length` (lazy `Promise.all`), `swings` optional ("--" acceptable for now; note), `lastActive` from newest session `started_at` or "--".
  - "Set as Active" button → `onSetActive(player)` (App calls `capture.selectPlayer({name,height_in,handedness})`, then `capture.refresh()`).
  - Add Player form: wire the inputs to local state (name, ft, in, hand). On Save → `createPlayer({name, height_in: ft*12+in, handedness})`, then `reload()` + `onAdded()`. Validate non-empty name; show inline error on reject. Keep markup.

### Task 9 — Sync + Connect screens

- [ ] Edit `web/frontend/src/pages/SyncScreen.tsx`. Props: `{ sessionId: number | null }`.
  - `const { data, loading, error, reload } = useApi(() => sessionId ? getProposals(sessionId) : Promise.resolve(null), [sessionId]);`
  - Build the rows from `data`: matched rows from `unmatched_*` + `proposals` is the available signal. Concretely:
    - For each `proposal` (a swing↔shot candidate): row with `confidence = Math.round(proposal.confidence*100)`, `status = confidence>=75 ? "matched" : "review"`, swing metrics chips from the swing (look it up in `unmatched_swings` by `swing_id`; show 1-2 metrics via `getSwing` is heavy — instead show `swing.club`/`created_at`), shot speed/carry from the matching `unmatched_shots` by `shot_id`.
    - For `unmatched_swings` with no proposal: `status="unmatched_swing"`, `shot=null`.
  - Header count: `${proposals.length} proposals — ${unmatched_swings.length} unmatched`.
  - "Confirm Match" (review rows) → `applyMatch(swing_id, shot_id).then(reload)`. "Unlink" → `unlinkSwing(swing_id).then(reload)`.
  - Empty state when `proposals.length===0 && unmatched_swings.length===0`: "All swings matched." Keep markup.

  > The seed leaves one live swing unmatched + matched ones; `propose_matches` will surface a proposal if a compatible unmatched shot exists. If the seed produces no proposals (timing-dependent), the unmatched-swing row still renders so Sync is non-empty. Acceptable for verification.

- [ ] Edit `web/frontend/src/pages/ConnectScreen.tsx`. Props: `{ captureStatus: CaptureStatus | null }`.
  - Replace the demo `setTimeout` → `connected` with the real `captureStatus.status`/`connected`. `status = captureStatus?.connected ? "connected" : "waiting"`. Show `last_error` if present under the indicator.
  - The 3-step wizard text stays static. The settings inputs (idle/units/port) stay local `useState` — add `{/* Phase 3: persist via a settings endpoint; local-only for now */}`. No backend call.

### Task 10 — Frontend unit test (the only new vitest beyond the Phase-1 smoke)

- [ ] Create `web/frontend/src/lib/api.test.ts` — pure unit tests (no network) for the load-bearing helpers:

```ts
import { describe, it, expect } from "vitest";
import { buildHistoryUrl } from "./api";
import { deltaVsBaseline, isEstimated, labelFor, heightToFtIn, METRIC_IDEAL } from "./format";

describe("api/format helpers", () => {
  it("buildHistoryUrl defaults context to impact (NOT overall)", () => {
    expect(buildHistoryUrl(1, "hip_sway_in")).toContain("context=impact");
    expect(buildHistoryUrl(1, "hip_sway_in")).not.toContain("overall");
  });
  it("deltaVsBaseline compares latest to mean of prior", () => {
    expect(deltaVsBaseline([{ value: 2 }, { value: 4 }, { value: 6 }]).delta).toBe(3); // 6 - mean(2,4)=3
    expect(deltaVsBaseline([{ value: 5 }]).delta).toBe(0);
    expect(deltaVsBaseline([]).value).toBe(0);
  });
  it("isEstimated flags low-confidence methods", () => {
    expect(isEstimated("foreshortening_2d;confidence=low")).toBe(true);
    expect(isEstimated("exact")).toBe(false);
  });
  it("labels + height + ideal map", () => {
    expect(labelFor("hip_sway_in")).toBe("Hip Sway");
    expect(heightToFtIn(72)).toBe("6' 0\"");
    expect(METRIC_IDEAL.hip_sway_in).toEqual([0, 2]);
  });
});
```

- [ ] Keep the existing `MetricCard.test.tsx` passing (its props are unchanged).

### Task 11 — Investigate + fix the 1 console error

- [ ] Build + serve, open the app, read the browser console. Likely candidates to confirm (do NOT assume — observe the actual error):
  1. **`recharts` `ResponsiveContainer` width(0)/height(0) warning** when the chart's flex parent has no resolved height (common with `flex-1` + `overflow`). Fix: give the chart wrapper an explicit `min-h`/height (the History hero already has `min-h-[300px]`, but the inner `flex-1` container may still warn) — wrap `ResponsiveContainer` in a `div` with a fixed height or `aspect` so it has non-zero dims on first paint.
  2. **External avatar image load failure** (`https://i.pravatar.cc/...`) → `net::ERR` / image errors in console when offline. Tasks 4/8 already drop pravatar `AvatarImage src` in favor of fallback initials — confirm this clears it.
  3. A **React key warning** or an `EventSource` connection error if the dev server proxy for `/events` isn't running (only in dev without uvicorn).
- [ ] Reproduce: run uvicorn (Task 12) + `npm run dev`, load `http://localhost:5173`, and capture the console. Identify the single root error, fix the root cause (not a `console.error` suppress), and **document in the final report**: what the error was, the file/line, and the fix.

> To read the console programmatically the implementer may use the Claude_Preview / browser MCP (`preview_console_logs`) after `preview_start` on the dev URL, or simply run the app and inspect. The orchestrator will also screenshot.

### Task 12 — GATES (build, tests, run-and-verify)

Run from repo root. Full Python path required (py launcher not on PATH). Use `& 'C:\Program Files\nodejs\npm.cmd'` if `npm` isn't on PATH.

- [ ] **Backend tests green** (incl. the new endpoint + helper):
  `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/ store/ -q`
  Expected: all pass (Task 2 added 2 store + 2 api tests).
- [ ] **Seed runs idempotently:**
  `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m web.backend.seed_dev` (twice; swing count stable at 3).
- [ ] **Frontend install** (if deps changed — none expected): `& 'C:\Program Files\nodejs\npm.cmd' install --prefix web/frontend`
- [ ] **Build gate (tsc + vite):** `& 'C:\Program Files\nodejs\npm.cmd' run build --prefix web/frontend`
  Expected: `tsc -b` no type errors, `vite build` writes `web/frontend/dist/`. Fix type errors minimally (no global `strict` loosening; `noUnusedLocals/Parameters` already off).
- [ ] **Vitest:** `& 'C:\Program Files\nodejs\npm.cmd' run test --prefix web/frontend`
  Expected: `MetricCard.test.tsx` + `lib/api.test.ts` pass.
- [ ] **RUN-AND-VERIFY** (real data renders):
  1. Start backend (it serves the built `dist/` at `/` and the API): in background
     `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m uvicorn web.backend.app:app --port 8000`
  2. Either load `http://localhost:8000/` (built dist) OR run `& 'C:\Program Files\nodejs\npm.cmd' run dev --prefix web/frontend` and load `http://localhost:5173/` (proxy → 8000).
  3. Confirm with the browser/preview MCP (or screenshots):
     - **Live:** the 6 MetricCards show seeded impact values (Hip Sway ~2.5"), the AI Coach Read headline = "Good power, but sliding hips…", BallClubStrip shows Ball Speed ~16x, Carry ~28x. (If the active player has no ready swing, the "Waiting" empty state shows — seed makes one ready, so expect data.)
     - **Players:** "Alex M." card, `6' 0"`, `RH`, marked Active.
     - **Sessions:** at least the seeded open session + the history session, real dates.
     - **History:** the hero line chart has the seeded `shoulder_tilt_deg` points (8+); trend cards populated.
     - **Sync:** at least one row (matched or unmatched).
     - **Connect:** indicator reflects real capture status.
  4. Stop the background uvicorn.
- [ ] **Console clean:** the single error from Task 11 is gone (note any benign remaining warnings in the report).

### Task 13 — Final verification + report (NO commit)

- [ ] Re-run superpowers:verification-before-completion: confirm EVERY gate command above was actually executed and its output observed.
- [ ] `git status`: new `seed_dev.py`, edited `api_swings.py`/`repo.py` + their tests, new `src/lib/*`, converted `useEvents.ts`/`useCapture.ts`, deleted `src/api.js`, edited screens/Topbar/App. `node_modules/` + `dist/` NOT staged.
- [ ] Do NOT commit; leave the tree for the orchestrator.
- [ ] Report: confirm all 7 screens + Topbar render real seeded data; list the backend addition; state what the console error was and how it was fixed; flag anything left local-only (Connect settings, History timeframe, Players total-swings, full Review swing picker).

---

## Notes / Risks

- **`context="overall"` is a trap.** Metrics never use `"overall"`; the prior `getHistory` default returned empty charts. All history/trend wiring + the seed use `"impact"`. This is the single most likely cause of "charts are blank" if the implementer keeps the old default.
- **Route ordering for `/api/swings/latest`** must precede `/{swing_id}` or it 422s. Verified the current file only has `/{swing_id}`.
- **Active player is server-side state** (`capture/status.active_player_id`) via the in-process supervisor singleton. With the dev seed but WITHOUT calling `POST /api/capture/active-player`, `active_player_id` may be `null` on a fresh boot → Live can't resolve a player. Mitigation: in `App.tsx`, if `active_player_id` is null but players exist, fall back to the first player's id for read-only screens (Live/History), and only set server-side active on explicit user action. Document this fallback. (Alternatively the seed could call the supervisor's `set_active_player`, but the seed uses a plain conn, not the running supervisor, so it cannot — hence the frontend fallback.)
- **SSE in production (single uvicorn worker):** `/events` polls the same store; fine for one bay. Multiple workers would each poll independently — out of scope.
- **`BallClubStrip`/`MetricCard` prop fidelity:** keep prop names EXACTLY (`name,value,unit,delta,deltaGood,idealRange,currentNum,isEstimated,highlight`). The Phase-1 smoke test asserts these; don't rename.
- **No new npm deps expected.** If any wiring needs one, add to `package.json` and call it out.
- **Media/video:** `source_video_path`/annotated media exist in the seed as paths but no real files — `SwingReplay` stays a placeholder, so no `/media` 404s from the UI. Don't point an `<img>`/`<video>` at seeded media paths.

---

## Appendix — component props (so wiring maps real data → these exactly)

- **MetricCard** `{ name: string; value: string|number; unit: string; delta: number; deltaGood: "up"|"down"|"neutral"; idealRange: [number,number]; currentNum: number; isEstimated?: boolean; highlight?: boolean }`
- **AIInsightCard** `{ headline: string; insights: Insight[]; highlight?: boolean }` where `Insight = { id; type: "mechanic"|"power"|"timing"|"warning"; text; metric; drill; severity: "good"|"neutral"|"bad" }`
- **SwingReplay** `{ highlight?: boolean }` (placeholder; no data wiring)
- **BallClubStrip** currently `()`; Task 5b adds `{ shot?: Shot | null }`
- **Topbar** (after Task 4) `{ players; activePlayerId; isPaused; r50Status; onPause; onResume; onSelectPlayer }`
- **Sidebar** `{ activeTab; setActiveTab }` (unchanged)
- **Avatar / AvatarImage / AvatarFallback**, **Badge**, **Button**, **Card**, **Tabs**, **Slider**, **Progress** — shared primitives, unchanged.
