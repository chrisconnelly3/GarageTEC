# Batch 1 — R50 Ingest: Live Shot Catcher + Persistence

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 1 rock (parallel with Camera+pose+chop). Depends on Batch 0 (data store).

---

## 1. Purpose

Turn the validated spike into the real, always-usable shot catcher: a friendly
app that connects to the Garmin R50 over GSPro Open Connect, captures every
shot, attributes it to the **active player**, groups shots into **per-player
sessions**, and **persists** everything to the data store — losing nothing.

## 2. Relationship to the spike

The spike (`spike/`) proved the GSPro Open Connect path and the novice wizard
UX. This rock **extracts the listener logic into reusable, GUI-agnostic code**
and adds persistence + multi-user. The spike stays as the validated throwaway;
this rock is the production catcher.

## 3. Scope

**In scope**
- GSPro Open Connect TCP listener (server on :921 + probe), reused from the spike.
- Parse each shot message → `store.models.Shot`.
- Multi-user **player profiles** (roster: name, height, handedness).
- **Active-player switch** in the UI; per-player **auto sessions** with idle
  timeout (default 15 min).
- Persist every shot via `store.repo`, tagged with active player + session.
- Reliability: buffer-on-failure so no shot is lost; auto-reconnect.
- Keep the friendly guided wizard UX from the spike for first connect.

**Out of scope**
- Matching a shot to its camera swing (the **Sync** rock does that).
- Camera/pose anything. AI coaching. History dashboards (the **Screen** rock).

## 4. Architecture (`catcher/` package)

| Module | Responsibility |
|---|---|
| `catcher/openconnect.py` | GUI-agnostic GSPro Open Connect listener (server + probe, JSON-stream framing, 201 handshake, 200 acks). Emits parsed message dicts via callback. Lifted from the spike. |
| `catcher/shotmap.py` | GSPro Open Connect JSON → `store.models.Shot` (ball/club columns + full `raw_json`). Distinguishes shots from heartbeats. |
| `catcher/sessionmgr.py` | Active-player state + per-player session resolution using `store.repo` (`get_open_session`/`create_session`/`end_idle_sessions`). |
| `catcher/persist.py` | Save a `Shot` via `store.repo.save_shot`; on DB failure, append raw to `data/pending_shots.jsonl` and retry on a timer (replay when DB recovers). |
| `catcher/app.py` | Tkinter GUI grown from the spike wizard: connect flow + live capture screen + "Who's hitting?" switch + Add-player + live shot feed + session/connection status. |
| `catcher/run.py` | Entry point; packaged to a standalone exe like the spike. |

Data flow: `openconnect` (raw msg) → `shotmap` (Shot or heartbeat) →
`sessionmgr` (attach active player + open/resumed session) → `persist`
(`save_shot`, buffered) → UI live feed updates.

## 5. Listener core (reused)

- Server listens TCP `0.0.0.0:921`; also a probe mode dialing the R50's IP, so
  either connection direction works (as proven in the spike).
- On connect: send `{"Code":201,...,"Player":{"Handed","Club"}}`; ack each
  inbound message with `{"Code":200}`.
- Tolerant JSON stream parser (handles newline-delimited AND concatenated
  objects — verified in the spike).
- Player handedness sent in the 201 should reflect the **active player's**
  handedness (from their profile) where the protocol allows.

## 6. Multi-user & sessions

- **Profiles:** roster via `store.repo.get_or_create_player` / `list_players`.
  Each profile carries `height_in` (drives that player's inch metrics later).
- **Active player:** UI tracks who is hitting; quick-switch buttons for the
  roster + an "Add player" form (name, height, handedness).
- **Per-player auto session** (on each captured shot):
  1. If no active player is selected, prompt / default to last used.
  2. `session = get_open_session(active_player) or create_session(active_player)`.
  3. `save_shot(shot with player_id + session_id)`.
  4. A periodic timer calls `end_idle_sessions(idle_minutes)` (default 15).
- This yields the required behaviour: brother hits → switch to you → you hit →
  switch back to brother within 15 min → his **same session resumes**; each
  person's shots stay theirs.

## 7. Reliability

- Every shot persisted immediately. If `save_shot` raises (e.g. DB locked),
  append the raw message + capture metadata to `data/pending_shots.jsonl`.
- A retry timer replays buffered shots into the store when it recovers; on
  success they're removed from the buffer.
- R50 disconnect → keep listening / reconnect; connection status shown in UI.
- SQLite WAL (from Batch 0) plus short-lived write handling avoids most locks.

## 8. Configuration

- `--port` (default 921), `--idle-minutes` (default 15), `--db` (store default),
  `--probe-ip` (default auto/gateway). Player heights live in profiles, not CLI.

## 9. Testing

- **openconnect:** loopback test (fake R50 client) → parsed messages, incl.
  concatenated-JSON framing (port the spike's loopback test).
- **shotmap:** representative GSPro Open Connect JSON → assert `Shot` fields +
  `raw_json` populated; heartbeat → no shot.
- **sessionmgr:** against an in-memory store, simulate interleaved shots from two
  players within and beyond the idle window → assert correct per-player session
  attribution and resume (the brother/you case).
- **persist:** simulate a failing store → assert shot buffered to file; then
  recover → assert replay + buffer cleared; assert no shot lost.
- **app:** construction smoke test (headless `--selftest`, like the spike).

## 10. Risks

- SQLite write contention if vision also writes concurrently → WAL + brief
  write transactions; buffer absorbs transient locks.
- R50 may send club data or ball-only (unconfirmed until field test) — `shotmap`
  stores whatever arrives + full `raw_json`; no field assumed mandatory.
- Active-player mis-selection → shots attributed wrongly. Mitigate: prominent
  current-player display + easy switch + (future) per-shot re-assign in UI.

## 11. Consumes (Batch 0 contracts)

`get_or_create_player`, `list_players`, `get_open_session`, `create_session`,
`end_idle_sessions`, `save_shot`. Produces `shot` rows tagged with `player_id` +
`session_id`; `swing_id` left null for the Sync rock.
