# Two-Camera 3D Reconstruction (GolfTEC-grade turn / X-factor / side-bend)

**Project:** GarageTEC
**Status:** Approved design (2026-06-04). **Deferred build** — start once the
GarageTEC sim/bay rig is set up (one physical prerequisite, §3). Validatable
*now* against `smooth_swing.mov`.
**Type:** New capability. Depends on Batch 0 (store), Batch 1 (camera/pose/chop —
the per-view 2D `PoseTimeline`s), Batch 2 (metrics registry + `MetricContext`).
Builds on the Phase-4 pro-reference work (`coach/norms/pro_reference/`,
`golftec_reference.json`).

---

## 1. Purpose

Recover **true 3D body rotation** from our two synced camera views so the app can
measure the metrics a single 2D view cannot — shoulder/hip **turn**, **X-factor**
(+ stretch), and **un-foreshortened side-bend** at the top and impact — and
compare a live swing to the **full** `golftec_reference.json`, not just the
square-position subset that 2D already handles.

This is what GolfTEC's OptiMotion does: the *same two camera angles we use*
(face-on + down-the-line), fused into 3D by triangulation. The Phase-4 monocular
spike (`.proref_work/turn3d_spike.py`) proved the turn signal is present
(down-the-line top-turn reached 95–108° on good clips) but that single-view
monocular depth is too noisy to ship (face-on top-turn 4° vs GolfTEC 89°).
**Triangulating two calibrated views is what makes it reliable.**

## 2. Why now is the right time to *spec* (not build)

The build needs a fixed, calibrated two-camera bay that does not exist yet. But
every algorithmic piece is designable now, and `smooth_swing.mov` (a direct-
export, already-synced side-by-side clip) lets us validate the whole pipeline
with the approximate calibration provider before the bay exists. So we write the
spec + plan now and execute when the rig is ready.

## 3. Prerequisites (physical — the USER does these once the bay is built)

> ⏳ **TRACKED REMINDER (user asked not to forget):** the production-accuracy path
> needs a one-time calibration capture in the finished bay.

1. **Fixed camera mounts.** Both cameras rigidly mounted; their relative geometry
   must not change after calibration (a bump invalidates it → recapture).
2. **Synced composite output.** The rig delivers the two views frame-synchronized
   — either a single side-by-side composite frame (as today's clips) or hardware
   genlock. (Per the capture-model decision; unsynced independent feeds are **out
   of scope** and would require a separate sync subsystem.)
3. **Calibration capture.** Film a checkerboard (or known-geometry target) from
   both views: a few dozen synced frames with the board at varied positions/
   angles spanning the hitting area, plus one known-scale reference. Run
   `CheckerboardCalibration` (OpenCV `stereoCalibrate`) once → save the calib
   file the pipeline loads. This is what makes the numbers match GolfTEC degree-
   for-degree; the approximate provider only gets close.

Until step 3 exists, the system runs on `AssumedGeometryCalibration` (approximate,
flagged lower-confidence).

## 4. Scope

**In scope (3D-only metrics — augment, never replace the 2D pipeline):**
- **`shoulder_turn_deg`, `hip_turn_deg`** at top + impact — true axial rotation
  vs target line. Same metric names as today, but `method="triangulated_3d"`
  (supersedes the existing `foreshortening_2d;confidence=low` estimates when 3D
  is available).
- **`x_factor_deg`** (shoulder turn − hip turn) at top, and **`x_factor_stretch_deg`**
  (peak X-factor in early downswing − X-factor at top). New metrics.
- **`shoulder_tilt_deg`, `hip_tilt_deg` at top + impact** — true 3D side-bend
  (un-foreshortened), `method="triangulated_3d"`. The existing 2D values stay for
  **address** and as the fallback when 3D is unavailable.

**Out of scope:**
- Replacing the working 2D metrics at square positions (address shoulder tilt
  already matches GolfTEC 10.5° vs 10°). 2D stays primary there + as fallback.
- A frame-sync subsystem (capture is assumed synced — §3.2).
- Segmentation/phase detection (Batch 1 already gives address/top/impact moments,
  reused as-is) and pose estimation changes (reuse MediaPipe per-view 2D).
- Kinematic sequence / velocities / ground-force (future).
- Live-camera capture plumbing (the existing recorded-video path is the input).

## 5. Capture & sync model

Input is the existing synced two-view source: a side-by-side composite split
50/50 into face-on (right) + down-line (left), exactly as `vision/pipeline.py`
does today. Because both views live in one synced frame, **corresponding frames
share a timestamp — triangulation needs no sync step.** The 3D path consumes the
two `PoseTimeline`s the existing pipeline already produces.

## 6. Calibration (pluggable)

A `Calibration` interface decouples the triangulation core from how camera
geometry is obtained. It yields, per view, a 3×4 **projection matrix**
(`P = K [R|t]`) and a shared **world frame** (origin, target-line axis, vertical
axis).

| Provider | Use | How |
|---|---|---|
| `AssumedGeometryCalibration` | dev now (`smooth_swing.mov`) + any uncalibrated ~90° rig | Assume the two cameras are orthogonal (face-on along depth, down-line along the target line), principal point at image center, a nominal focal length; set metric **scale** from anthropometry (`shoulder_width_m ≈ 0.24 × player.height`). Vertical from the address-pose gravity/spine direction; target line from the down-line camera axis. Approximate → results flagged `confidence=medium`. |
| `CheckerboardCalibration` | production bay (after §3.3) | Load a saved OpenCV `stereoCalibrate` result (intrinsics `K1,K2` + distortion, extrinsics `R,t`) → projection matrices. World frame from the calibration target placement (board aligned to target line / ground). Results `confidence=high`. |

The provider is selected by config; the triangulation core is identical for both.

## 7. Architecture (`vision/threed/` + new metric defs)

| Module | Responsibility |
|---|---|
| `vision/threed/calibration.py` | The `Calibration` interface + the two providers (§6). Returns `P_face_on`, `P_down_line` (3×4) and the world frame. Pure/loadable; no video. |
| `vision/threed/reconstruct.py` | `reconstruct(face_on: PoseTimeline, down_line: PoseTimeline, calib) -> Pose3DTimeline`. Per frame, per landmark: take the two views' 2D landmark + visibility; if both ≥ vis threshold, triangulate (`cv2.triangulatePoints`, then de-homogenize) into metric 3D; weight/skip low-visibility landmarks; temporally smooth (centered moving average, reuse the Batch-2 smoothing idea). Handles anatomical L/R correspondence (MediaPipe labels by the person's anatomy, consistent across views; a calibration flag covers a mirrored view). |
| `vision/threed/types.py` | `Pose3DTimeline` (per-frame `list[Landmark3D]` with metric x,y,z + confidence) + `Landmark3D`. |
| `metrics/defs/rotation_3d.py` | `shoulder_turn_deg`, `hip_turn_deg` (3D), `x_factor_deg`, `x_factor_stretch_deg`. |
| `metrics/defs/sidebend_3d.py` | 3D `shoulder_tilt_deg`/`hip_tilt_deg` at top + impact. |

The existing 2D `vision/` and `metrics/defs/*` are untouched; 3D is additive.

## 8. World frame & 3D angle definitions

Define a swing frame: **X** = target line (toward target), **Z** = vertical (up),
**Y** = depth (face-on viewing axis), from the `Calibration` world frame.

- **Turn (shoulder/hip):** project the shoulder-line vector (left→right shoulder)
  onto the ground plane (X-Y); its signed angle about Z **relative to the address
  frame** = turn. Top ≈ 89° closed (shoulders), 48° (hips); impact ≈ 48° / 42°
  open. Measured relative to address, so it is robust to small world-frame error.
- **X-factor:** `shoulder_turn − hip_turn` at a given instant. `x_factor_deg` at
  **top**; `x_factor_stretch_deg` = (max X-factor over early-downswing frames,
  top→impact) − (X-factor at top). (Literature: stretch, not top value,
  discriminates skill.)
- **Side-bend (shoulder/hip tilt, 3D):** tilt of the shoulder/hip line within the
  torso's frontal plane (vs vertical), computed in 3D so it is **not**
  foreshortened by rotation. Reported at top + impact (the positions 2D
  under-reads). GolfTEC: shoulder 36° @ top / 39° @ impact; hip 11° / 14°.

## 9. Metric defs & confidence

- Same metric **names** as the 2D versions (`shoulder_turn_deg`, `hip_turn_deg`,
  `shoulder_tilt_deg`, `hip_tilt_deg`); the `method` field distinguishes
  source: `"triangulated_3d;confidence=high"` (checkerboard) or
  `"triangulated_3d;confidence=medium"` (assumed geometry). When 3D is
  unavailable, the existing 2D rows remain (rotation stays
  `foreshortening_2d;confidence=low`; tilt at top/impact stays 2D).
- New metrics `x_factor_deg`, `x_factor_stretch_deg` (3D-only; absent without 3D).
- Idempotent recompute (Batch-2 semantics): clear + re-insert the swing's metrics.
  Where both a 2D and a 3D value exist for the same (name, context), the 3D row
  wins for display; the coach prefers the higher-confidence method. (The `metric`
  table has no uniqueness constraint on (name, context) — rows differing only by
  `method` coexist, so the 2D and 3D values are both retained for audit and the
  consumer selects by `method`/confidence.)

## 10. Store change

New table mirroring `pose_frame`:

```
pose_3d_frame(swing_id, frame_index, landmarks JSON)   -- landmarks: [{name,x,y,z,confidence}], meters
```
Repo additions: `save_pose_3d_frames(swing_id, frames)`, `get_pose_3d_frames(swing_id)`,
`clear_pose_3d_frames(swing_id)`. A dedicated table (per the data-analysis
preference) keeps 3D metric coords cleanly separate from the 2D pixel `pose_frame`
rows.

## 11. Integration

- **Pipeline:** after the existing build-both-`PoseTimeline`s step, if 3D is
  enabled and a `Calibration` is available, call `reconstruct(...)` and persist
  the `Pose3DTimeline` via `save_pose_3d_frames`. No change when 3D is off.
- **`MetricContext`:** add `pose_3d` (frame_index → `list[Landmark3D]`) +
  `pose_3d_at(kind)` (reuses the moment-frame lookup). The 3D metric fns read it
  at address/top/impact; they no-op (return `[]`) when `pose_3d` is empty, so the
  registry runs unchanged with or without 3D.
- **Coach / `golftec_reference.json`:** the 3D metrics are exactly the `needs_3d`
  entries. When a 3D value is present, the coach compares it to the GolfTEC target
  (turn vs 89°, X-factor vs ~41°, side-bend vs 36°/39°); when absent, the
  `two_d_comparable_now` gate still limits comparison to square positions. No
  schema change to the reference — just more entries become live.

## 12. Testing

- **Synthetic closed-loop (core correctness, no video):** build a known 3D
  skeleton, rotate it by a known angle about vertical, project to two virtual
  cameras with known `P` matrices, run `reconstruct` → assert recovered 3D ≈
  ground truth and computed turn = the known angle (within tolerance). Also drives
  X-factor and side-bend from constructed poses.
- **Calibration providers:** `AssumedGeometryCalibration` returns sane orthogonal
  `P` matrices + scale; `CheckerboardCalibration` loads a saved calib fixture and
  reproduces its `P` matrices.
- **`smooth_swing.mov` fixture (real synced clip, approximate calib):** end-to-end
  → assert shoulder turn @ top is plausible (~80–95°) and hips < shoulders
  (positive X-factor). Validates the real pipeline today.
- **GolfTEC acceptance:** on known-good swings, shoulder turn @ top within
  tolerance of 89° and hip turn within tolerance of 48° (looser for the
  approximate provider; tighter once checkerboard-calibrated).
- **Metric defs:** synthetic `MetricContext` with hand-built `pose_3d` → assert
  expected turn/X-factor/side-bend + correct `method`/confidence; assert the fns
  no-op cleanly when `pose_3d` is empty.

## 13. Risks

- **Approximate calibration is rough** → flagged `confidence=medium`; the
  checkerboard path (§3.3) is the accuracy fix; turn is measured *relative to
  address* so it tolerates world-frame error better than absolute side-bend.
- **2D landmark noise → 3D** → visibility-weighted triangulation, temporal
  smoothing, optional RANSAC/outlier rejection on the triangulated track.
- **Occlusion at the top** (trail arm/club hides a shoulder/hip) → confidence-gate
  per landmark; lean on the view with better visibility; interpolate short gaps.
- **L/R correspondence / mirrored view** → MediaPipe labels by anatomy
  (consistent across views); a calibration flag handles a horizontally-mirrored
  feed.
- **`smooth_swing.mov` is rotated 90° + uncalibrated** → dev fixture only; rotate
  to landscape; validate *trends and ranges*, not exact degrees, until the bay
  checkerboard exists.
- **Synced-composite assumption** → if production ever ships unsynced feeds, a
  sync subsystem is needed (explicitly out of scope).

## 14. Consumes / Produces

- **Consumes:** the two per-view `PoseTimeline`s (Batch 1), swing moments
  (address/top/impact), player height (anthropometric scale for the approximate
  calibration), `golftec_reference.json` targets (coach).
- **Produces:** `pose_3d_frame` rows; 3D metric rows (`shoulder_turn_deg`,
  `hip_turn_deg`, `x_factor_deg`, `x_factor_stretch_deg`, 3D
  `shoulder_tilt_deg`/`hip_tilt_deg` @ top/impact); live comparisons against the
  `needs_3d` half of the GolfTEC reference; a "vs tour pro" panel input for the
  Review screen (benchmarking build).

## 15. Build order (when un-deferred)

1. `vision/threed/types.py` + `calibration.py` (AssumedGeometry first).
2. `reconstruct.py` + the synthetic closed-loop tests (prove triangulation).
3. `pose_3d_frame` store table + repo fns.
4. Pipeline integration (persist 3D when enabled) + `MetricContext.pose_3d`.
5. `metrics/defs/rotation_3d.py` + `sidebend_3d.py` + tests.
6. Validate on `smooth_swing.mov`; wire coach comparison to the `needs_3d`
   GolfTEC entries.
7. **(After bay built)** `CheckerboardCalibration` + the §3 capture → switch the
   provider → re-validate against GolfTEC tolerances.
