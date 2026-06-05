# GarageTEC — Session Handoff (2026-06-05)

**Purpose:** Continue in a FRESH session (this one is near context max). The
auto-memory (`project_garagetec_plan.md`) loads the full project history; this doc
adds the active state + exact next steps. Everything below is **committed to
`main`** (github.com/chrisconnelly3/GarageTEC) and tested.

---

## ▶ Resume prompt (paste into the new session)

> Read `docs/handoff/2026-06-05-session-handoff.md` first. The full GarageTEC
> software arc is built (3D pipeline, in-app two-camera calibration, body + ball
> "vs tour pro" benchmarking). Pick up from the "Open / next" list — likely a new
> feature I'll name, or wiring something for when the physical bay exists.

---

## What this session accomplished (all on `main`, all tested)

A long build arc, in order. **Every item was TDD'd and committed.** Test totals:
~247 python + ~22 frontend green; frontend `npm run build` clean.

1. **Phase-4 pro reference (A+B)** — commits `36f8a7f` (+ research docs):
   - **B (deep literature):** cited, adversarially-verified biomechanics report →
     `docs/research/2026-06-04-pro-biomechanics-literature.md`. Headline: only
     side-bend@impact (+maybe hip tilt) are 2D-face-on-viable; **all rotation/
     X-factor is 3D-only**; sway/head/hand-depth have NO published norms.
   - **A (GolfDB pro reference):** pipeline `coach/norms/pro_reference/`
     (manifest→build→aggregate) → `pro_reference.json` (99 swings/84 pros).
     Pose-based view auto-detect (~18% of GolfDB view labels are wrong) +
     acute-magnitude tilt fold. CC BY-NC: only derived numbers vendored.
   - **GolfTEC AUTHORITATIVE reference** `golftec_reference.json`
     (`build_golftec_reference.py`) — hand-transcribed Tour Averages + SwingTRU,
     trusted over GolfDB on conflict; each (metric,phase) tagged
     `two_d_comparable_now`. Cross-check doc: our 2D matches at address,
     under-reads at top/impact (foreshortening). `coach/golftec.py compare()`.

2. **Two-camera 3D pipeline (Tasks 1–10)** — commits `ebbb5b1..cb683e6`:
   `pose_3d_frame` table + `Landmark3D`; `vision/threed/` (types, calibration with
   `AssumedGeometryCalibration`, `reconstruct` via `cv2.triangulatePoints`,
   pipeline3d); `metrics/geometry3d.py` + `MetricContext.pose_3d` +
   `metrics/defs/rotation_3d.py` (turn, X-factor, stretch) + `sidebend_3d.py`
   (3D tilt@top/impact), all `method=triangulated_3d`, **no-op without pose_3d**
   so the 2D path is untouched. Spec+plan in `docs/superpowers/`.

3. **In-app two-camera calibration** — commits `62f57c5..0e0c4cc` + fixes:
   self-service **"Camera Calibration" card on the Connect screen**. First live
   camera ingestion (`LiveCameraSource` + `DualCameraSource` combining two USB
   cams in software), checkerboard engine, `CheckerboardCalibration` (completes
   3D-plan Task 11), `calibration` store table, `CalibrationSupervisor`,
   `/api/calibration/*` (MJPEG preview + SSE), camera **auto-detect with friendly
   names** (pygrabber), **two device dropdowns** (down-line / face-on),
   **varied-angle pose collection** (15 min / 24 auto-run / 30 max; accept on new
   (position cell, tilt bucket)), single-camera **mono test mode**, auto-run at
   target, history+activate. `process_video` **auto-uses the active calibration**.
   - **Bugfix `744831d` (via /systematic-debugging):** mono mode was never
     actually implemented — `detect_board` always split the frame, so a single
     webcam (one centered board straddling the split) detected in neither half.
     Fixed with a real mono path.

4. **UI polish** — commits `304ac9b`, `a4e8f5f`: nav logo enlarged + local asset;
   **green token corrected to the real logo green `#79BC30`** (was `#84CE39`;
   WCAG AA verified 8.4:1 with near-black text). `docs/garagetec-hardware-
   shopping-list.md` written + mini-PC right-sized (8–16GB/256–500GB, no GPU).

5. **Benchmarking — body** — commit `764366b`: `coach.golftec.benchmark_metrics`
   + **"vs Tour Pro" panel** on Review (you/tour/Δ, "NEEDS 3D" badge for rotation
   + top/impact, gated until calibration). Swing-detail API returns `benchmarks`.

6. **3D sanity check** — commit `5ef0171`: ran the committed
   `scripts/validate_3d_smooth_swing.py` on landscape smooth_swing.mov →
   111 frames reconstructed, **X-factor@top 47° (tour-accurate)**, absolute turn
   inflated under approximate calibration (expected). Fixed the script (sys.path
   + honest verdict).

7. **Benchmarking — ball** — commit `678c934`: `coach/ball_reference.py` =
   **TrackMan PGA Tour Averages** per club + `benchmark_ball`. Researched GSPro
   Open Connect → only **7 comparable** metrics (ball/club speed, smash[derived],
   launch/VLA, spin, attack angle, carry); **Max Height + Land Angle excluded**
   (not in the protocol). **Club recorded per shot** (`club` on Shot + idempotent
   migration `db._add_column_if_missing`). `CaptureSupervisor.active_club` tags
   shots; API `GET /api/capture/clubs`, `POST /api/capture/active-club`. Frontend
   **ClubSelector on Live** + **BallBenchmarkPanel** on Live + Review.

---

## Current state

- **Branch:** `main`, clean, all pushed-worthy (commit/push only on user ask).
- **App runs:** `python -m web.backend.seed_dev` then
  `python -m uvicorn web.backend.app:app --port 8000` → http://localhost:8000.
  (A dev server is typically left running on 8000; restart it after frontend
  rebuilds. `*.mp4`, `.proref_work/`, `.uvicorn_8000.log` are gitignored.)
- **The whole "vs ideal" story is in place:** body mechanics → GolfTEC (3D-gated)
  + ball data → TrackMan (per club). 3D metrics show "NEEDS 3D" until the bay is
  calibrated, then light up automatically.

## Open / next (nothing blocking; pick per the user)

- **Physical bay (user, hardware):** build from `docs/garagetec-hardware-shopping-
  list.md`; mount + fix two USB cameras (120fps); run the in-app calibration
  (Connect → Camera Calibration) per `docs/guides/bay-camera-calibration-guide.md`
  → the 3D "NEEDS 3D" rows light up.
- **Optional software follow-ups (not yet built):**
  - Surface the R50 fields we now store but don't compare (back/side spin,
    face-to-target, club path) as raw values (no TrackMan column for them).
  - Live-swing capture through the pipeline (the `LiveCameraSource`/
    `DualCameraSource` foundation exists; wiring real-time swing capture +
    sync is the bigger future piece — see the 3D spec's sync caveat).
  - History/trends for ball metrics vs tour over time.
  - The 1 benign frontend console error (pre-existing, low priority).

## Key gotchas / env

- **Python 3.12:** `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`
  (`py`/`python` NOT on PATH — use the full path). **Node:** `C:\Program Files\nodejs`.
- **Build pattern:** spec/plan in `docs/superpowers/` → TDD (often subagent-driven
  per task) → verify (run tests + browser screenshot) → commit. Frontend tests
  live as `src/**/*.test.tsx` (NOT `__tests__/`); `npm test` = `vitest run`.
- **Frontend changes need `npm run build` + a server restart** to show in the
  served app (backend serves `web/frontend/dist`, which is gitignored / built).
- **CRLF warnings on commit are benign** (Windows line endings).
- **Store migrations:** `init_db` runs `schema.sql` (CREATE TABLE IF NOT EXISTS)
  then `_add_column_if_missing` for columns added to existing tables (e.g.
  `shot.club`). Add future column-adds there.
- **Docs index:** specs/plans in `docs/superpowers/`, research in `docs/research/`,
  guides in `docs/guides/`, hardware list + handoffs in `docs/`.
