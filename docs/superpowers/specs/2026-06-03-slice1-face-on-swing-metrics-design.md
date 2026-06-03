# Slice 1 — Face-On Swing Metrics from Recorded Video

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Thin vertical slice / pilot for the spec → agent → review delegation loop

---

## 1. Purpose

Prove the core body-tracking chain end to end on a recorded swing video:

> split frame → pose the face-on half → auto-find address/top/impact → compute shoulder tilt + hip sway at each → render an annotated video + numbers.

This is the smallest piece that demonstrates "what did the body do." It also acts
as the **pilot** for the project's delegation model (one spec, one worktree, one
agent build, one review) and as the thin proof of the larger Camera+Pose,
Swing-Chop, and Metrics rocks. It deliberately does **not** include a database,
UI, R50 data, or the down-the-line view.

## 2. Success Criteria

- Running the CLI on `golf swing.MOV` produces, with no manual frame picking:
  - an annotated `.mp4` showing the body skeleton, the three detected moments
    labelled, and the metric values burned in;
  - `address.png`, `top.png`, `impact.png` keyframe images;
  - a `metrics.json` with frame number + timestamp for each moment and the
    metric values.
- The three moments are detected in the correct order (address < top < impact)
  and land on visually correct frames (verified by eyeballing the annotated
  video, then locked as a regression check).
- Shoulder tilt is reported in degrees; hip sway is reported in inches (plus
  pixels and %-of-shoulder-width as backup).
- Runs on CPU on a normal Windows laptop in a reasonable time (target: a ~18 s
  clip processed in well under a minute is nice-to-have, not a hard requirement).

## 3. Scope

**In scope**
- Single recorded side-by-side video input (left = down-the-line, right = face-on).
- Use the **face-on (right) half only** for metrics.
- Assume **exactly one swing per clip** (pick the dominant motion burst if needed).
- 2D pose via MediaPipe (BlazePose, 33 landmarks).
- Detect three moments: address, top of backswing, impact.
- Two metrics, both face-on: **shoulder tilt** and **hip sway**.
- File-based output (no database).

**Out of scope (later rocks/slices)**
- Down-the-line metrics, true camera calibration, R50 launch data, sync,
  AI coaching, database, dashboard/UI, multi-swing clips, trend history,
  live capture, 3D pose.

## 4. Input

- Container: QuickTime `.MOV` (validated sample: 1920×1080, ~30 fps, ~18.3 s,
  ~560 frames, slow-motion).
- Layout: side-by-side, **left half = down-the-line**, **right half = face-on**.
- Frame split point is **configurable** (default 0.5 = midpoint) so other clips
  and the future DTL slice plug in without code changes.
- The code must read fps/resolution/frame count from the file (via OpenCV), not
  assume the sample's values.

## 5. Tech Stack

- Python 3.12 (already installed at
  `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`).
- OpenCV (`opencv-python`) — video read/write, drawing.
- MediaPipe Pose — 2D landmarks.
- NumPy — math/smoothing.
- CPU only. CLI script (no GUI this slice).
- Dependencies pinned in `vision/requirements.txt`.
- **Risk to verify at build:** MediaPipe wheel availability for Python 3.12; if
  it fails, fall back to a 3.11 virtualenv. Decide and document at build time.

## 6. Architecture

A small package `vision/` with focused modules, each independently testable:

| Module | Responsibility | Key interface (shape, not final signature) |
|---|---|---|
| `video.py` | Open clip, iterate frames, crop a view half. | `frames(path) -> iterator of (index, time_s, full_bgr)`; `crop_face_on(full_bgr, split=0.5) -> bgr` |
| `pose.py` | Wrap MediaPipe; frame → landmarks. | `landmarks(bgr) -> Pose33 | None` (per-landmark x,y in pixels + visibility) |
| `segment.py` | Landmark timeline → 3 moment indices. | `find_moments(timeline) -> {address:int, top:int, impact:int}` |
| `metrics.py` | Landmarks (+address ref + scale) → numbers. | `shoulder_tilt(pose) -> deg`; `hip_sway(pose, address_pose, ppi) -> {inches, px, pct}` |
| `scale.py` | Pixels-per-inch from height + address pose. | `ppi_from_height(address_pose, height_in) -> float` |
| `render.py` | Draw skeleton + labels + numbers → mp4/pngs. | `render(frames, timeline, moments, metrics, outdir)` |
| `run.py` | CLI entry; orchestrates; writes output folder. | `python -m vision.run --video "golf swing.MOV" --height 72` |

**Data flow**

```
video.frames ─► crop_face_on ─► pose.landmarks (per frame)
        │                              │
        └──────────────► landmark timeline (list over frames, with gaps handled)
                                       │
                          segment.find_moments ─► {address, top, impact}
                                       │
        scale.ppi_from_height(address) ─┤
                                       ▼
                          metrics at each moment ─► render + metrics.json
```

The timeline is a list (length = #frames) of `Pose33 | None` (None where pose
not found). Landmark series are smoothed (small moving average, e.g. 3–5 frames)
before segmentation and metrics to reduce jitter.

## 7. Segmentation (2D heuristics, tuned on the sample)

All from face-on pose. Use wrist landmarks (lead + trail) as the swing proxy
since we have no club.

- **Address:** the long low-motion window at the start. Compute per-frame total
  landmark velocity (sum of keypoint displacements); address = a representative
  frame in the last sustained calm stretch before motion ramps up.
- **Top of backswing:** within the first big motion phase, the frame where the
  wrists reach their highest point (minimum image-y) / where vertical wrist
  velocity crosses from upward to downward.
- **Impact:** during the downswing, the frame where the wrists return to roughly
  the address hand height while wrist speed peaks (fast through the bottom).
  Slow-motion makes this distinct.
- Guardrails: enforce ordering address < top < impact; if detection is
  ambiguous, fall back to the largest motion burst as the swing and pick
  extrema within it. Log what was chosen.

These are heuristics; expected to need tuning against the sample clip. After
visual validation, the detected frame indices for `golf swing.MOV` are recorded
as a regression expectation (± a few frames tolerance).

## 8. Metrics

**Shoulder tilt** (exact, no calibration)
- Angle of the line from left-shoulder to right-shoulder landmark vs horizontal,
  in degrees. Sign indicates which shoulder is higher.
- Reported at address, top, impact.

**Hip sway** (estimated inches + backups)
- Hip center = midpoint of left/right hip landmarks.
- Horizontal displacement of hip center from its **address** position.
- **Pixels → inches** via an anthropometric ruler from the player's height:
  - `shoulder_px` = pixel distance between shoulder landmarks at address.
  - `real_shoulder_in ≈ 0.24 × height_in` (e.g. 0.24 × 72 = 17.28 in).
  - `ppi = shoulder_px / real_shoulder_in`.
  - `sway_in = hip_center_dx_px / ppi`.
- Also report raw **pixels** and **% of shoulder width** as calibration-free
  backups.
- **Direction/sign:** positive = **toward target**. Target side is inferred as
  the net horizontal hip direction during the downswing (top → impact); a
  `--target-side {left,right}` override is available if inference is wrong.
- Reported at address (0 by definition), top, impact, and as **max sway**.
- **Accuracy is explicitly an estimate (~±0.3–0.5 in).** GolfTEC achieves true
  inches via calibrated camera geometry; we approximate via height + body ratio.
  A real-calibration upgrade is a later slice. `metrics.json` records the method
  and the assumed ratio so the estimate is auditable.

## 9. Output

Written to `swings/<YYYYMMDD_HHMMSS>/` (this folder is gitignored):

- `annotated.mp4` — face-on video with skeleton overlay, a label when the current
  frame is address/top/impact, and a final/persistent readout of the metrics.
- `address.png`, `top.png`, `impact.png` — the three keyframes with skeleton +
  values drawn.
- `metrics.json` — schema:
  ```json
  {
    "source_video": "golf swing.MOV",
    "video": {"width": 1920, "height": 1080, "fps": 29.98, "frames": 562},
    "split": 0.5,
    "height_in": 72,
    "scale": {"method": "shoulder_ratio_0.24", "shoulder_px": 0.0, "ppi": 0.0},
    "moments": {
      "address": {"frame": 0, "time_s": 0.0},
      "top":     {"frame": 0, "time_s": 0.0},
      "impact":  {"frame": 0, "time_s": 0.0}
    },
    "metrics": {
      "shoulder_tilt_deg": {"address": 0.0, "top": 0.0, "impact": 0.0},
      "hip_sway": {
        "unit_inches": {"top": 0.0, "impact": 0.0, "max": 0.0},
        "unit_px":     {"top": 0.0, "impact": 0.0, "max": 0.0},
        "unit_pct_shoulder": {"top": 0.0, "impact": 0.0, "max": 0.0},
        "toward_target_is": "left"
      }
    }
  }
  ```

## 10. Configuration (CLI)

- `--video PATH` (required)
- `--height IN` (default 72)
- `--split FLOAT` (default 0.5)
- `--view {face_on,full}` (default face_on; `full` for debugging the split)
- `--target-side {auto,left,right}` (default auto)
- `--out DIR` (default `swings/`)

## 11. Testing

- **Unit (metrics/scale):** synthetic `Pose33` inputs with known geometry →
  assert exact shoulder-tilt degrees and hip-sway px/inches; assert `ppi`
  formula.
- **Unit (segment):** synthetic timelines (a hand y-curve that goes up then down)
  → assert address < top < impact at expected indices.
- **Characterization/regression:** run on `golf swing.MOV`; after one human
  eyeball pass, lock the detected moment frames (± tolerance) and metric values
  (± tolerance) as a regression test.
- **Smoke:** end-to-end run creates `annotated.mp4`, three PNGs, and a valid
  `metrics.json`.
- Note pose inference is nondeterministic-ish across versions; tolerances, not
  exact equality, for video-derived values.

## 12. Repo Layout

```
vision/
  __init__.py
  video.py  pose.py  segment.py  scale.py  metrics.py  render.py  run.py
  requirements.txt
  tests/
    test_metrics.py  test_scale.py  test_segment.py  test_smoke.py
swings/            # outputs, gitignored
docs/superpowers/specs/2026-06-03-slice1-face-on-swing-metrics-design.md
```

## 13. Risks & Mitigations

- MediaPipe / Python 3.12 wheel — verify; fall back to 3.11 venv.
- Heuristic moment-finding fragile to tempo/clip differences — tune on sample,
  log choices, keep thresholds in named constants for easy adjustment.
- Pose jitter — smooth landmark series before use.
- Inch estimate is approximate — labelled as estimate, method recorded in JSON,
  real calibration deferred.
- Single-swing assumption — if the clip has multiple swings, pick the dominant
  motion burst and log it.

## 14. Relationship to the Bigger Build

Slice 1 is intentionally files-only and face-on-only. The fuller rocks
(Camera+Pose with both views, Swing-Chop with all 8 phases, Metrics brain with
the full metric set, Data store, Sync, AI coach, Screen) are specced separately
and built in dependency-ordered batches via worktrees + branches. The module
boundaries above are chosen so this slice's `pose.py`/`metrics.py`/`segment.py`
grow into those rocks rather than being thrown away.
