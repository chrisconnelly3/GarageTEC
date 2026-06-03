# Batch 1 — Camera + Pose + Swing-Chop (full)

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 1 rock (parallel with R50 ingest). Depends on Batch 0 (data store).

---

## 1. Purpose

Turn video into stored, per-swing body data: ingest a video (both views), run
2D pose on each view, **auto-detect every swing**, segment each swing into the
**8 phases**, and persist each swing + its pose timeline + phase moments to the
data store. This is the production-grade version of Slice 1, and the foundation
the Metrics brain and Screen rocks build on.

## 2. Core principle — the swing is the atomic unit

R50 shots, body metrics, AI analysis, and review are all **per swing**, and the
product goal is feedback **immediately after each swing**. Therefore this
pipeline's output unit is a single **swing record**. A video may contain 1..N
swings; the pipeline detects each and emits one swing record per swing. The same
code path serves recorded files now and live capture later (each swing emitted
as soon as it completes).

## 3. Scope

**In scope**
- Input: **recorded video** now (incl. the side-by-side `golf swing.MOV`), both
  views (left = down-the-line, right = face-on). Structured so live dual-camera
  capture bolts on later behind the same frame-source interface.
- 2D pose (MediaPipe) per view, per frame.
- **Multi-swing detection** within a video.
- **8-phase segmentation** per swing: address, takeaway, lead-arm-parallel, top,
  transition, shaft-parallel-down, impact, early follow-through.
- Persist per swing: `swing` row, `pose_frame`s (both views, the swing's frame
  range), `moment`s (the 8 phases), and media (source ref; optional annotated
  clip for immediate review).
- Streaming-friendly design (emit per-swing as detected).

**Out of scope**
- **Metric computation** (the Metrics brain rock consumes pose+moments).
- **Live camera capture + hardware sync** (deferred; interface ready).
- Shot↔swing matching (the Sync rock). AI, dashboards.

## 4. Architecture (`vision/` package — extends Slice 1)

| Module | Responsibility |
|---|---|
| `vision/frames.py` | Frame source abstraction. `VideoFileSource(path, split)` yields `(index, time_s, view_crops)` where `view_crops = {"down_line": bgr, "face_on": bgr}`. A future `LiveCameraSource` implements the same interface. |
| `vision/pose.py` | MediaPipe pose per view crop → `list[Landmark]` (pixels + visibility). One detector instance per view. |
| `vision/swing_detect.py` | From a per-frame motion signal (wrist/hand velocity energy), find swing windows `[(start_idx, end_idx), ...]` bounded by stillness. 1..N per video. |
| `vision/segment.py` | Within one swing window, detect the 8 phases (per view where appropriate). Extends Slice 1's 3-moment logic. Returns `list[Moment]`. |
| `vision/persist.py` | For each detected swing: `add_swing`, `save_pose_frames` (both views, window range), `save_moments`, `save_media`. |
| `vision/render.py` | Optional: annotated per-swing clip (skeleton + phase labels) for immediate review; saved as media. Shared with Slice 1. |
| `vision/pipeline.py` | Orchestrate: frames → pose(both views) → swing_detect → per swing(segment → persist → optional render). Emits a `SwingResult` per swing via callback (for immediacy/live). |
| `vision/run.py` | CLI: `python -m vision.run --video <path> --player <name> [--session <id>]`. |

## 5. Data flow

```
VideoFileSource ─► pose(down_line) + pose(face_on)  [per-frame, both views]
        │
        ├─► motion signal ─► swing_detect ─► [swing windows]
        │
        └─► for each swing window:
               segment (8 phases, per view) ─► moments
               add_swing(player_id, session_id, source, fps, w, h, view_layout)
               save_pose_frames(swing_id, "down_line", frames[window])
               save_pose_frames(swing_id, "face_on",   frames[window])
               save_moments(swing_id, moments)
               [optional] render annotated clip ─► save_media
               emit SwingResult(swing_id, moments, frame_range)
```

Pose runs once per frame per view and is cached; windows just slice the cached
timeline, so multi-swing videos aren't re-posed per swing.

## 6. Swing detection

- Build a per-frame **motion energy** signal from lead+trail wrist landmark
  speed (and overall keypoint displacement), smoothed.
- A **swing window** = a contiguous high-energy burst flanked by low-energy
  (still) stretches, with a minimum duration and a minimum peak (reject fidgets).
- Merge/clip windows so each contains exactly one backswing→through-swing arc.
- For a single-swing clip → one window (consistent with Slice 1). For a range
  video → many. Log the count and per-window frame ranges.

## 7. 8-phase segmentation (per swing window)

2D heuristics over the cached pose; use the view that reads each phase best.
- **address:** last still frame before takeaway (energy ~0).
- **takeaway:** first sustained rise in hand motion away from address.
- **lead-arm-parallel (backswing):** lead-arm vector (shoulder→wrist) crosses
  horizontal during backswing.
- **top:** hands reach highest point / vertical hand-velocity reversal.
- **transition:** first downward hand motion after top.
- **shaft-parallel-down:** approximated (no club) from lead forearm/hand crossing
  horizontal on the downswing — flagged lower-confidence (club-dependent in
  reality).
- **impact:** downswing frame where hands return to ~address height at peak
  speed (slow-mo makes this crisp).
- **early follow-through:** fixed short interval after impact / hands rising past
  address height post-impact.
- Enforce monotonic ordering; where a phase can't be found confidently, store it
  with a confidence flag rather than guessing silently. Constants live in one
  place for tuning. Down-the-line view aids spine/forearm phases; face-on aids
  height/reversal phases.

## 8. Persistence & player attribution

- A processed video belongs to a **player** (and a session). `run.py` takes
  `--player` (resolved via `store.repo.get_or_create_player`) and an optional
  `--session` (else `get_open_session`/`create_session`). Each swing stored with
  that `player_id` + `session_id`.
- `view_layout` recorded on the swing (e.g. `side_by_side_LR`) so views are
  reconstructable.
- Live mode later will attach the active player like the catcher does.

## 9. Immediacy / live-ready

- The pipeline emits a `SwingResult` as soon as a swing window closes (not only
  at end-of-file), so a future live source yields per-swing body data right after
  the swing — meeting the "immediate after each swing" goal.
- `frames.py` is the only module that differs between recorded and live; the
  rest is reused unchanged.

## 10. Testing

- **frames:** split geometry correct on `golf swing.MOV` (both crops sized
  ~960×1080); index/time monotonic.
- **pose:** returns landmarks on a sample frame; handles a no-person frame
  (returns empty) without crashing.
- **swing_detect:** synthetic motion signals (one burst; three bursts; a fidget)
  → assert correct window count and rough ranges.
- **segment:** synthetic pose timeline with a known hand-height curve → assert
  the 8 phases found in order; missing-phase path sets the confidence flag.
- **persist:** against in-memory store → one video with two synthetic swings
  yields two `swing` rows, pose_frames for both views, 8 moments each.
- **pipeline smoke:** run on `golf swing.MOV` → ≥1 swing stored with both-view
  pose + moments; eyeball optional annotated clip; lock counts as regression.

## 11. Risks

- 8-phase 2D detection is the hard part; several phases are club-dependent
  (shaft-parallel) → approximate + confidence-flag, refine with 3D later.
- MediaPipe Python 3.12 wheel (shared risk with Slice 1) — verify; fallback 3.11.
- Multi-swing boundary errors on noisy/long videos → conservative thresholds +
  logged windows + a `--single-swing` override for known one-swing clips.
- Pose cost on long videos (CPU) — pose once per frame, cache, slice windows.

## 12. Relationship to Slice 1 & Metrics rock

Slice 1 is the thin files-only pilot (face-on, 3 moments, metrics+render bundled)
and stays as the pilot. This rock generalizes its `frames/pose/segment/render`
modules to both views + 8 phases + multi-swing and **stores to the DB instead of
files**. **Metric computation moves OUT** to the Metrics brain rock (Batch 2),
which reads `pose_frame`s + `moment`s and writes `metric`s — keeping this rock to
"video → stored body data".
