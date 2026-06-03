# Batch 4 — Screen / UI

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 4 rock (parallel with AI coach). Depends on Batch 0–4 (reads everything; calls Sync).

---

## 1. Purpose

The window into GarageTEC: a local web app that shows each swing the moment it's
processed (video + skeleton + body numbers + ball/club data + AI read), plus
swing review, session summaries, history/trends, manual sync correction, and
player-profile management. Viewable on the bay TV/monitor or a phone over the
local network.

## 2. Platform

- **Backend:** FastAPI (Python, `uvicorn`) reading the Batch 0 store + calling
  the Sync rock. Serves the REST API, a live event stream, and media files.
- **Frontend:** React (Vite build) served as static files by the FastAPI app
  (single origin → no CORS). Charts via a lightweight lib (e.g. Recharts); an
  HTML5 video player for clips.
- Runs on the mini PC; reachable at `http://<minipc-ip>:<port>` on the LAN.

## 3. Live updates (immediacy)

- The capture→pose→metrics→sync→coach pipeline writes to the store. The backend
  detects newly-completed swings by **polling the store** on a short interval
  (e.g. 1–2 s) for swings whose metrics + coaching are ready since the last seen
  id, and pushes a **Server-Sent Events** (`/events`) notification.
- The frontend's live view subscribes to `/events` and refetches the new swing's
  detail → the just-hit swing appears within seconds. (SSE chosen over WebSocket:
  one-way, simpler, sufficient.)

## 4. Screens (v1 core, expandable)

- **Live / Last swing:** annotated clip, key metrics each with *vs your baseline*
  and *vs ideal* + confidence flags, ball/club data, the AI headline + findings +
  drills. Auto-updates on new swing.
- **Swing review:** scrub the clip with skeleton overlay, the 8-phase timeline
  (moments), full metric table, full AI feedback, the matched shot.
- **Session view:** the session's swings (per player), session AI summary, quick
  metric trends within the session.
- **History / trends:** per-metric line charts over time via `swing_history`,
  filterable by player + club.
- **Sync fix:** lists unmatched swings/shots + Sync's proposed matches with
  confidence; confirm / re-assign / unlink (calls the Sync rock).
- **Players:** manage the roster (name, height, handedness) — same store rows the
  catcher uses.

## 5. Architecture

```
web/
  backend/
    app.py          # FastAPI app: mounts API + static frontend + media
    api_players.py  api_sessions.py  api_swings.py  api_history.py  api_sync.py
    events.py       # SSE stream + store-polling watcher
    media.py        # serve files from data/media (path-safe)
    deps.py         # store connection per request
  frontend/         # React (Vite)
    src/ ... pages: Live, SwingReview, Session, History, SyncFix, Players
  tests/
    test_api_*.py   # FastAPI TestClient over an in-memory store
```

| Component | Responsibility |
|---|---|
| `api_*` routers | Thin read endpoints over `store.repo` returning JSON for each screen; write endpoints for profiles, notes, and sync actions. |
| `events.py` | Poll store for newly-ready swings; emit SSE `swing_ready` events. |
| `media.py` | Stream `annotated.mp4` / keyframes / source clips from `data/media` with path traversal protection. |
| `api_sync.py` | Wrap the Sync rock: `propose`, `apply_match`, `unlink`. |
| React pages | The six screens above; a shared API client + an SSE hook. |

## 6. Key API (illustrative)

- `GET /api/players` · `POST /api/players` · `GET /api/sessions` ·
  `GET /api/sessions/{id}` · `GET /api/swings/{id}` (metrics+moments+shot+
  coaching+media) · `GET /api/history?player=&metric=&context=` ·
  `GET /api/sync/proposals?session=` · `POST /api/sync/apply` ·
  `POST /api/sync/unlink` · `GET /events` (SSE) · `GET /media/{...}`.

## 7. Immediacy path (end to end)

```
swing hit ─► (catcher saves shot) + (vision stores swing+pose+moments)
        ─► metrics computed ─► sync links shot ─► coach writes coaching
        ─► backend poll sees ready swing ─► SSE swing_ready
        ─► frontend Live view fetches /api/swings/{id} ─► shows it (~seconds)
```

## 8. Scope

**In scope:** the six screens, SSE live updates, media serving, sync-fix UI,
profile management, responsive layout (TV + phone).

**Out of scope:** authentication / multi-tenant (single-household LAN), cloud
hosting, native mobile apps (responsive web suffices), editing pose/metrics by
hand (review only), external benchmark comparison UI beyond the norms the AI
coach already applies.

## 9. Testing

- **Backend (FastAPI TestClient over in-memory store):** each endpoint returns
  the expected shape for seeded data; `GET /api/swings/{id}` aggregates metrics +
  moments + shot + coaching; history endpoint returns ordered points;
  media path traversal is rejected; `events` emits `swing_ready` when a new
  ready swing appears (watcher tested against a seeded store, not wall-clock).
- **Sync endpoints:** call into the Sync service (real, with in-memory store) →
  apply/unlink mutate links.
- **Frontend:** a build smoke (`vite build` succeeds) + a couple of component
  tests for the metric card (renders value + vs-baseline + confidence flag) and
  the SSE hook; deep UI testing deferred.

## 10. Risks

- Polling interval vs load → short interval is cheap on SQLite for a single
  household; make it configurable; upgrade to a push notify later if needed.
- Media path security → serve only from `data/media`, reject `..` traversal.
- Frontend scope creep → ship the six core screens; defer fancy visualizations.
- React build/tooling overhead on the mini PC → frontend is prebuilt to static
  files; the mini PC only runs FastAPI + serves static assets.

## 11. Consumes

All store read APIs (`list_players`, `get_swing`, `get_metrics`, `get_moments`,
`get_coaching`, `get_media`, `swing_history`, `list_swings`, sessions), the Sync
rock (`propose`/`apply`/`unlink`), and serves `data/media` files. Writes:
profiles, notes, and sync corrections.
