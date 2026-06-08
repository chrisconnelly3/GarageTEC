# GarageTEC — Session Handoff (2026-06-07)

Continues `docs/handoff/2026-06-05-session-handoff.md`. Read `CLAUDE.md` (user global
instructions) and the auto-memory at
`C:\Users\chris\.claude\projects\C--Users-chris-Documents-Golf\memory\MEMORY.md`
first — they cover the product, the build plan, and the R50 live-data spike.

GarageTEC = local, single-user, touch-first golf swing-analysis app for a home bay.
FastAPI + SQLite backend, React + TS + Vite + Tailwind frontend. Ingests Garmin R50
data (GSPro Open Connect, TCP 921), captures two-camera swing video, runs pose → 2D/3D
metrics, benchmarks "vs Tour Pro" with a stoplight, plus an AI coach.

Repo: `C:\Users\chris\Documents\Golf` — on `main`, pushed to
`github.com/chrisconnelly3/GarageTEC` (**PRIVATE**). Everything below is committed & pushed.

---

## What shipped this session

1. **AI coach output reformat.** Model stays `claude-sonnet-4-5` (best quality/$). UI now
   shows a one-line headline + a tight 2–3-sentence worst-offender summary (no number
   recitation, no bullet/drill list). `coach/prompt.py` steers it; `findings`/`drills` are
   still generated server-side as the anti-hallucination grounding gate, just not displayed.

2. **Stricter stoplight thresholds + clean demo data.** `coach/metric_thresholds.py`
   tightened (green = tour-tight). Fixed the demo seed (`web/backend/seed_demo.py`): it now
   **wipes before seeding** (was appending → polluted DB) and the matched demo shot carries
   believable amateur offsets, so the stoplight shows a real green/yellow/red mix.
   **NOTE:** new thresholds require a **server restart** to take effect (the long-lived
   process caches the module + a DB snapshot).

3. **Live screen UX → merged into a unified "Swing" screen (BIG: just completed).**
   Spec: `docs/superpowers/specs/2026-06-07-unified-swing-screen-design.md`.
   Plan (all 9 tasks DONE): `docs/superpowers/plans/2026-06-07-unified-swing-screen.md`.
   - `LiveScreen` + `ReviewScreen` → one **`SwingScreen`** (`web/frontend/src/pages/SwingScreen.tsx`),
     both old files deleted. One state `selectedSwingId: number|null` (null = **Following**
     latest, id = **Pinned**). New `SwingControlBar` (LIVE-pill-as-Go-Live + ‹ › arrows +
     dropdown) atop the left column. New-shot count = index of pinned swing in the
     newest-first list (no separate counter).
   - R50 status moved OUT of the header: dot on the Start/End Session button (Topbar), loud
     inline waiting/disconnected state in the swing area, red badge on the gear/Connect
     sidebar icon. Sidebar item renamed Live→**Swing**, Review removed.
   - History/Sessions **deep-link** into Swing pinned (App `openSwing(id)`).
   - `SwingReplay` got a "video not kept for this swing" placeholder (graceful pruned-video).
   - 86 frontend tests pass, build clean, browser-verified.

4. **Position stepper + phase calibration.** 8 swing positions, **evenly spaced** with a
   **variable-speed playhead**; labels edge-anchored. Demo seed emits all 8 moments at
   frame-verified times for `smooth_swing.mov`.

5. **Header logo** cropped tight + enlarged, dead-center of the viewport (rendered in
   `App.tsx`, not Topbar, to dodge the header's backdrop-filter containing block).

6. **Pose backend → RTMPose (replaced MediaPipe for the skeleton overlay).** Deep-research
   picked RTMPose (top-down). `vision/pose_rtm.py` = `RTMPoseEstimator` (API-compatible with
   `vision/pose.py`'s `PoseEstimator`), detect-once + per-frame pose. `make_pose_estimator()`
   factory + `vision/constants.py` `POSE_BACKEND` (**default "mediapipe"**; overlay uses
   RTMPose via the regenerated sidecar). Models in `models/` (gitignored), fetched from a
   **HuggingFace mirror** (openmmlab host is geo-blocked here); SHA-256 logged at load.
   Overlay sidecar `smooth_swing.pose.json` (COCO-17) at repo root + copied to media on seed.
   **Known limit:** top-of-backswing arm overlap is a single-view 2D ceiling (RTMPose AND
   ViTPose both lose a hand there) — the real fix is **multi-view triangulation in the bay**
   (documented in the checklist). Arms are correct at address/downswing/impact/finish.

7. **R50 spike tool now Mac-compatible.** `spike/gspro_spike_listener.py` is pure-stdlib +
   cross-platform "open folder" + logs to Desktop on macOS. `spike/Start Spike Listener.command`
   launcher. A **GitHub Actions** workflow (`.github/workflows/build-mac-spike.yml`) builds a
   double-click `.app` on GitHub's Mac runners (Actions → "Build R50 Spike Listener (macOS)"
   → Run workflow → download the `R50-Spike-Listener-mac` artifact). Fixed a stuck build:
   `macos-13` (Intel) runners are retired → switched to `macos-latest`; build now succeeds.

8. **R50 status dot** got a `ring-2 ring-[#0A0D0B]/50` so the green "connected" dot is
   visible on the green Start-Session button.

---

## Current runtime state

- **Dev server is RUNNING:** `python -m uvicorn web.backend.app:app --port 8000` (from repo
  root). Serves the prebuilt `web/frontend/dist` + the API at `http://127.0.0.1:8000/`.
  There is **no Vite dev server** in use — frontend changes need `npm run build` (in
  `web/frontend`) for the running server to serve them, then a browser hard-refresh
  (`Ctrl+Shift+R`) because the JS bundle is cached.
- **Demo DB** seeded (3 players; Alex M. is the rich one). Reseed:
  `python -m web.backend.seed_demo` (WIPES + rebuilds; regenerates real coaching for Alex's
  latest matched swing if `ANTHROPIC_API_KEY` is set). `.env` at repo root (gitignored) holds
  the key. After reseed OR threshold changes, **restart the uvicorn server** (it caches a DB
  snapshot / the thresholds module).

---

## Open / pending (good next steps)

1. **User is mid UI/UX review, screen by screen.** Live/Swing is done & merged; they just
   restarted the server to look at it. Likely next: review **History, Sessions, Players,
   Sync, Connect** screens for the same polish treatment. (They tend to invoke `/ux` for
   critique and `/brainstorming` → `/writing-plans` → subagent-driven for builds.)
2. **Brother's Mac architecture — BLOCKING the spike test.** The macOS `.app` build is now
   **arm64** (`macos-latest` is Apple Silicon). Fine for M1/M2/M3/M4. **If his Mac is Intel,
   the arm64 app won't launch** → switch the workflow to a **universal2** PyInstaller build
   (`--target-arch universal2`; needs a universal2 Python on the runner — some setup). Ask
   the user which Mac he has.
3. **Video retention / pruning spec — NOT YET DONE (next planned feature).** Decoupled from
   the merge. Keep metrics/coach/pose forever (tiny); prune VIDEO on a policy (last-N
   sessions / starred-only / older-than-X), with a storage view on Connect. The Swing screen
   already degrades gracefully when a swing's video is absent.
4. **Minor:** the SwingScreen code-quality review left two intentionally-skipped Minor notes
   (video-state reset asymmetry on dropdown/arrow vs goLive; `isEstimated(null)` inherited
   constant call) — revisit only if relevant.

## When the real bay + GPU arrive — see `docs/bay-verification-checklist.md`
It's the durable "verify on real hardware" list. Highlights: directional **sway sign +
handedness** (top item); **RTMPose cutover** (install `onnxruntime-gpu`, flip
`POSE_BACKEND="rtmpose"` so metrics use it too; a GTX 1050 Ti/1060 suffices); **calibrate the
two cameras** (uncalibrated 3D metrics are physically wrong — verified); **tune the stoplight
on real calibrated swings**; **verify model SHA-256** vs official before shipping;
**multi-view overlay fix** for top-of-swing arms.

---

## Gotchas / conventions for the next session

- **Caveman ultra** is the user's global default (CLAUDE.md), but this entire project has run
  in normal detailed prose and the user expects that here — keep prose.
- **Windows + git-bash:** `gh api` paths must OMIT the leading slash (bash rewrites
  `/repos/...` to a filesystem path). LF→CRLF git warnings are benign.
- **Bash tool:** foreground `sleep` is blocked; use `run_in_background: true` + an
  `until <check>; do sleep N; done` loop to wait. Long builds/extractions → background.
- **Commit style:** end messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Commit to `main` (the user has consented all session). Push when done.
- **Pose models / `models/`, `pose_ab.py`, `sc_tmp.html`, `.superpowers/`** are gitignored.
- Frontend tests: `cd web/frontend && npx vitest run`. Single file: `npx vitest run <path>`.
  Typecheck: `npx tsc --noEmit`. The jsdom canvas warning from `PoseOverlay` in tests is noise.

## Key files
- Unified screen: `web/frontend/src/pages/SwingScreen.tsx`,
  `web/frontend/src/components/SwingControlBar.tsx`; wiring in `web/frontend/src/App.tsx`,
  `components/Topbar.tsx`, `components/Sidebar.tsx`.
- Pose: `vision/pose_rtm.py`, `vision/pose.py` (`make_pose_estimator`), `vision/constants.py`
  (`POSE_BACKEND`), `web/backend/extract_pose.py` (overlay sidecar generator).
- Coach: `coach/prompt.py`, `coach/backend.py`, `coach/metric_thresholds.py`.
- Seed: `web/backend/seed_demo.py`. Spike: `spike/`, `.github/workflows/build-mac-spike.yml`.
