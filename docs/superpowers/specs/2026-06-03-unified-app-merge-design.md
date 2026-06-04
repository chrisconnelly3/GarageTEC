# Unified App — Merge Catcher into the Dashboard

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Architecture change. Folds the R50 capture app into the web dashboard so there is ONE self-contained, touch-first app.

---

## 1. Purpose

Today GarageTEC has two front-ends: the **catcher** (Tkinter desktop app that
runs the R50 GSPro Open Connect listener and saves shots) and the **dashboard**
(FastAPI + React review UI). For best UX we want **one app to launch**: the
dashboard runs the R50 capture engine itself, so capture + review + coaching all
live in one place, operated by touch.

This is feasible with low risk because the catcher's capture engine
(`catcher/openconnect.py`, `shotmap.py`, `sessionmgr.py`, `persist.py`) was
built GUI-agnostic. The merge reuses those modules and retires only the Tkinter
shell.

## 2. Scope

**In scope**
- Run the R50 listener inside the FastAPI app (background thread).
- Capture controls: **auto-start on launch**, plus **Pause/Resume** (take casual
  swings without recording, app stays open).
- Capture API + live SSE push (status, shots, player changes).
- Information architecture for the merged app: **left sidebar** nav + a
  **persistent global bar** (player switch, R50 status, pause).
- **Live screen content hierarchy** (below).
- A **Connect** screen (port the catcher's friendly wizard).
- Retire the Tkinter shell; keep the engine modules.
- A single **kiosk launcher**.

**Out of scope**
- Visual styling / design system (Tailwind + shadcn + MagicPatterns) — a
  separate pass. This spec wires functionality; pages may look plain until then.
- Any change to vision/metrics/sync/coach logic, or the store schema.
- Live camera capture (still recorded-video for now).

## 3. Approach

Run the listener in a **background daemon thread** owned by the FastAPI app,
reusing the existing engine as-is. Rejected alternatives: rewriting the socket
code as asyncio (risk + discards proven code), or a separate process (defeats
"one app"). The catcher already ran this engine in a thread, so this is a small,
proven move.

## 4. UX / Information Architecture

**User & context:** a golfer (often the less-technical brother) at the bay,
gloved, glancing at a **touchscreen** between shots; wants instant feedback with
near-zero fiddling, plus occasional deeper review.

### 4.1 Persistent global bar (visible on every screen)
Three things are needed constantly during practice, so they are always one tap
away (recognition over recall; Fitts's Law — large, reachable):
- **Who's hitting** — large player switcher (tap to switch mid-session; resumes
  that player's session per the existing sessionmgr logic).
- **R50 status chip** — Waiting / Connected / Paused / "N shots" (visibility of
  system status).
- **Pause/Resume capture** — safety valve: paused keeps the R50 connected but
  discards incoming shots (not persisted, not analyzed), clearly labeled
  "Paused — not recording" (user control & freedom).

### 4.2 Left sidebar (touch rows ≥56px), ordered by frequency
1. **Live** — default/home; the during-practice screen (see 4.3).
2. **Review** — deep-dive one swing: scrub video + skeleton, 8-phase timeline,
   full metric table, full AI feedback, matched shot.
3. **History** — per-metric trends over time.
4. **Sessions** — past practice blocks + session summaries.
5. **Players** — manage profiles (name, height, handedness).
6. **Sync** — review/fix swing↔shot matches (occasional).
7. **Connect / Settings** (pinned bottom) — R50 connect wizard + settings (rare
   after first setup).

### 4.3 Live screen content hierarchy (priority — important)
The big projector the golfer hits into already shows **ball + club** prominently
(R50 is wired to it). So the dashboard prioritizes what the projector does NOT
show — body mechanics, AI, and replay — to avoid redundancy:
- **Hero — swing replay video:** the just-hit swing with **realtime ⇄ slow-mo**
  toggle + scrub, and a **skeleton overlay** on/off. Largest element.
- **Primary — body-movement metrics:** the body numbers (tilt, sway, spine
  angle, early extension, hand depth, rough turns), each vs the player's
  **baseline / ideal**, with low-confidence flags surfaced.
- **Primary — AI read:** headline + key findings + a drill.
- **Secondary — ball + club strip (compact, de-emphasized):** ball speed, spin,
  launch, carry; club speed, path, face, AoA. Present for context + AI
  correlation, but visually minor (it's already big on the projector).

### 4.4 Touch & states
- Targets ≥48px; no hover-only menus; destructive actions (delete player)
  confirm. Player switch = large tappable cards.
- Empty/failure states: "Waiting for R50…", "No swings yet — take a shot",
  "R50 disconnected — tap to reconnect", "Paused — not recording".
- Peak-end: a satisfying "✓ Shot captured" with metrics animating in; the
  session-end summary as the closing moment.

## 5. Technical Architecture

### 5.1 `web/backend/capture.py` — `CaptureSupervisor`
- Owns an `OpenConnectListener` (from `catcher.openconnect`) in a **daemon
  thread**, with its **own** `sqlite3` connection (`check_same_thread=False`,
  WAL) — never shares the request connection.
- On each parsed message (callback from the listener):
  - If **running** and the message is a shot (`shotmap.map_message` returns a
    Shot): resolve active player + session via `catcher.sessionmgr`, persist via
    `catcher.persist` (buffer-on-failure), then emit a capture event.
  - If **paused**: still ack the R50 (keep it connected) but **discard** — no
    persist, no analyze.
  - Heartbeats: update status only.
- State: `status` (stopped/listening/connected/paused), connected client, active
  player id, shot count, last error.
- Methods: `start()`, `stop()`, `pause()`, `resume()`, `set_active_player(id)`,
  `restart()`. **Auto-restart** the listener thread on unexpected death.
- After a shot is persisted, calls `sync.SyncService.on_new_shot(...)` to attempt
  incremental matching to an already-stored camera swing in the same
  (player, session), then emits the SSE event. (Metrics + AI coach run off the
  vision pipeline per camera swing, NOT off shot arrival — a shot only adds ball/
  club data and a possible swing link.)

### 5.2 Lifecycle
- FastAPI **lifespan** startup → `supervisor.start()` (auto-on).
- Shutdown → `supervisor.stop()` (close listener + connection cleanly).
- A module-level singleton supervisor, exposed via `deps` for the API routers.

### 5.3 `web/backend/api_capture.py`
- `GET  /api/capture/status` → current supervisor state.
- `POST /api/capture/pause` · `POST /api/capture/resume` · `POST /api/capture/restart`.
- `POST /api/capture/active-player` `{player_id}` → set active player.

### 5.4 SSE
Extend the existing `/events` stream (and `SwingWatcher`) to also push **capture
events**: `shot_received`, `capture_status` (connected/paused/disconnected),
`active_player_changed`. The Live screen subscribes and updates instantly
(no polling for capture state).

### 5.5 Concurrency / safety
- Listener thread + its own DB connection (WAL) — the catcher's buffer-on-failure
  persistence already absorbs transient locks.
- `paused` and `active_player` are thread-safe flags (lock or `threading.Event`).
- Supervisor start/stop is idempotent.

## 6. Retire (delete)
- `catcher/app.py` (Tkinter wizard), `catcher/run.py`, `catcher/build_exe.md`.
- Keep: `catcher/openconnect.py`, `shotmap.py`, `sessionmgr.py`, `persist.py`
  and their tests (the reusable engine). Update any imports the deleted files
  exposed. (The spike under `spike/` is untouched — already a retired artifact.)

## 7. Kiosk launcher
A single launcher (e.g. `run_garagetec.cmd` / small exe) that:
1. starts `uvicorn web.backend.app:app` (chosen port),
2. waits for health, then
3. opens the default browser **fullscreen/kiosk** at the app URL on the
   touchscreen.
Documented so the mini PC can auto-launch it on boot later.

## 8. Frontend changes (functional only; styling deferred)
- Add the **persistent global bar** (player switch + status + pause) wired to
  `/api/capture/*` + SSE.
- Restructure nav into the **left sidebar** (the 7 areas).
- Rework the **Live** page to the 4.3 hierarchy (replay hero with speed/skeleton
  controls, body metrics, AI read, compact ball/club strip), updating live via
  SSE.
- Add the **Connect** screen porting the catcher wizard's steps (R50 → Connect →
  GSPro; join Wi-Fi; troubleshooting), shown on demand / when disconnected.
- Existing Review/History/Sessions/Players/Sync pages remain; only nav placement
  changes.

## 9. Testing
- **CaptureSupervisor** (in-memory store + a fake listener feed): shot persists
  when running; **discarded when paused**; correct player/session attribution;
  status transitions; auto-restart on simulated thread death.
- **Capture API** via FastAPI TestClient: status/pause/resume/active-player
  mutate supervisor state; pausing stops persistence.
- **SSE**: capture events emitted on shot/status/player change (seed-driven, no
  wall-clock sleeps).
- **Retirement**: suite stays green after deleting the Tkinter shell (no import
  breakage); engine module tests still pass.

## 10. Risks
- Single process → a crash pauses capture too. Mitigations: daemon-thread
  auto-restart, buffer-on-failure persistence, supervisor isolation from request
  handling. Acceptable for a single-bay setup.
- Thread/DB contention → dedicated listener connection + WAL + existing buffer.
- Pause must not drop the R50 connection (only discard shots) — explicit in 5.1.

## 11. Relationship to other work
- The **design-system / MagicPatterns** pass restyles these same screens
  (Tailwind + shadcn, touch-first); this spec defines the IA + functionality it
  will dress. The Live hierarchy here is the brief for that hero screen.
- The **swing-segmentation tuning** follow-up is independent.
