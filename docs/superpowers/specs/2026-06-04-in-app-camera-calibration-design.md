# In-App Two-Camera Calibration (self-service, Connect screen)

**Project:** GarageTEC
**Status:** Approved design (2026-06-04).
**Type:** New capability. Depends on the two-camera 3D work (`vision/threed/`,
`coach/golftec.py`, the `pose_3d` metrics — all on main). **Subsumes deferred
Task 11** (`CheckerboardCalibration` is built here). Introduces the first
**live-camera ingestion** (the foundation for future live swing capture).
**Validatable now** (synthetic + a laptop-webcam smoke test); full stereo
accuracy needs the real two-camera bay.

> **REVISION 2026-06-04 (post-build, after webcam testing):** two decisions
> evolved during use and are now the source of truth (superseding the original
> §3–§5/§9 text below):
> 1. **Capture = TWO separate USB cameras, not a hardware composite.** The bay
>    uses two USB cameras (down-line + face-on); a new `DualCameraSource`
>    combines their streams into the side-by-side composite **in software** (so
>    everything downstream is unchanged). This reverses the earlier "synced
>    composite / one device" + "software-combine out of scope" decisions. Sync
>    caveat: the two cameras free-run independently → fine for a still
>    checkerboard, small timing skew for fast live-motion later (body rotations
>    tolerate it; club-speed precision would want hardware sync). The UI has
>    **two camera dropdowns** populated by **`list_cameras()`** (friendly names
>    via pygrabber/DirectShow). Single-camera **mono** mode (webcam smoke test)
>    uses one camera + whole-frame detection.
> 2. **Varied-angle pose collection (15–30).** Instead of one pose per position
>    cell (max 12), a pose is accepted only if it adds a new **(position cell,
>    tilt bucket)** combo — `estimate_tilt_deg` (solvePnP w/ guessed intrinsics)
>    buckets the board tilt. `MIN_RUN_POSES=15`, `TARGET_POSES=24` (auto-run),
>    `MAX_POSES=30`, `TILT_BUCKET_DEG=12`. The UI shows poses/target + tilt-angle
>    variety and prompts the user to tilt the board.

---

## 1. Purpose

Let anyone recalibrate the bay's two cameras **entirely inside the app** — no
command line, no coding agent — so a bumped/moved camera is a 5-minute self-serve
fix. A "Camera Calibration" card on the Connect screen: live preview with
detected-corner overlay + a coverage map, Start/Stop capture, Run, a quality
readout, Export, and re-calibrate. The result (`bay_calib.json`) is what the 3D
pipeline loads to produce GolfTEC-accurate turn / X-factor / side-bend.

> Note (UI): in the MagicPatterns design, **Connect and Settings are one screen**.
> The calibration card lives there, alongside the existing R50/port settings.

## 2. Why the app can do this with no middleman

Calibration is pure OpenCV compute (`cv2.findChessboardCorners` +
`cv2.stereoCalibrate`) — already in `scripts/calibrate_bay_cameras.py`. We promote
that logic into a module and wrap it in a backend service + UI. No AI, no human
hand-off. Export remains as an optional backup/debug escape hatch, not a required
step.

## 3. Scope

**In scope**
- **`LiveCameraSource`** (first live `FrameSource`) over a configurable capture
  device.
- **Checkerboard calibration engine** (detect → coverage → `stereoCalibrate` →
  `bay_calib.json` + reprojection error), incl. the **`CheckerboardCalibration`
  provider** (completes Task 11) loading the active calibration.
- **`CalibrationSupervisor`** (threaded capture/detect service, mirrors
  `CaptureSupervisor`).
- **`calibration` store table** + repo (history + active selection).
- **`/api/calibration/*`** endpoints incl. **MJPEG preview** + **SSE status**.
- **Connect-screen "Camera Calibration" card** (live preview overlay, coverage
  map, good-pose counter, Start/Stop, Run, result, Export, history/activate).
- **Wire-up:** the 3D pipeline uses the active `CheckerboardCalibration` when one
  exists (else `AssumedGeometry`).
- A **single-camera test mode** so the live flow is exercisable on a laptop webcam.

**Out of scope**
- Live *swing* capture/processing in the app (the `LiveCameraSource` foundation is
  built here, but wiring live swings through `process_video` is a separate effort).
- Auto-detecting camera hardware / multi-bay management.
- The physical checkerboard + keeping cameras fixed (operator's job; see the guide).
- Coverage-map threshold final tuning (needs real bay frames — a known follow-up).

## 4. Capture model + the live-camera foundation

The bay combines both cameras into one **synced side-by-side composite** exposed
as a video device (e.g. HDMI→USB capture card seen as a webcam). New
`vision/frames.py::LiveCameraSource(device_index, split)` implements the existing
`FrameSource` interface (`frames()` generator of `FrameSample`, `.width/.height/
.fps`, `close()`), reusing `split_views()` to produce the two views. It also
exposes the **raw composite frame** (calibration needs both halves with their
pixel corners, not just crops).

**Single-camera test mode:** when configured for one webcam, the source treats the
whole frame as the composite and runs detection on it (the resulting calibration
is geometrically meaningless with one camera, but it exercises device I/O,
real-frame detection, preview, coverage, and SSE end-to-end).

## 5. Calibration engine (`vision/threed/checkerboard.py`)

Pure, testable functions (no web, no device):
- `detect_board(composite, cols, rows, split) -> BoardDetection` — find the
  checkerboard in each half; returns per-view corner arrays, a `found_both` flag,
  a **sharpness/fullness** judgment (`is_good_pose`), and the board-center
  position per view.
- `coverage_cell(center, image_size, grid=(4,3)) -> (col,row)` — which coverage
  grid cell the board occupies (drives the coverage map + "cover the corners").
- `stereo_calibrate(object_points, fo_pts, dl_pts, image_size, square_m) ->
  CalibrationResult` — `cv2.calibrateCamera` per view then `cv2.stereoCalibrate`;
  returns intrinsics, extrinsics, **reprojection error**, and the `bay_calib.json`
  dict (the shape `CheckerboardCalibration` loads). Square size accepts inches
  (×25.4) — and only sets metric scale; **angles are scale-invariant**.
- `scripts/calibrate_bay_cameras.py` becomes a thin CLI over this module (no
  duplicated logic).

`CheckerboardCalibration` (Task 11) is added to `vision/threed/calibration.py`,
loading the active `bay_calib.json`.

## 6. Capture service (`web/backend/calibration.py`)

`CalibrationSupervisor` (mirrors `CaptureSupervisor`’s thread-safe pattern):
- `start(device_index, cols, rows, square_mm)` → opens `LiveCameraSource` in a
  daemon thread; per frame: `detect_board`, and if `is_good_pose` and the pose is
  *new* coverage (debounced so a held-still board doesn't spam duplicates),
  accumulate the corner pair + mark the coverage cell. Publishes live status to a
  `CalibrationEventBus` (SSE) and keeps the latest overlay frame for the MJPEG
  preview.
- `stop()` → stop the thread, keep accumulated poses.
- `run()` → `stereo_calibrate` on the accumulated poses → persist a `calibration`
  row → activate → return the result (or an error if < 8 good poses).
- `status()` → capturing?, good-pose count, coverage grid, last detection,
  device/params.
- Singleton via `deps.get_calibration_supervisor()` (like `get_supervisor`).

## 7. Store (`calibration` table)

```
calibration(id, created_at, device_index, cols, rows, square_mm,
            n_poses, reprojection_error, calib_json TEXT, is_active INTEGER)
```
Repo: `save_calibration(...)`, `get_active_calibration()`,
`list_calibrations()`, `set_active_calibration(id)` (clears other actives).
The 3D pipeline reads the active row’s `calib_json`.

## 8. API (`web/backend/api_calibration.py`, prefix `/api/calibration`)

Mirrors `api_settings.py` (APIRouter, pydantic, `Depends`); registered in
`app.py` via `include_router`.

| Method · path | Purpose |
|---|---|
| `POST /start` `{device_index, cols, rows, square_mm}` | begin capture |
| `POST /stop` | stop capture |
| `POST /run` | calibrate accumulated poses → save + activate → result |
| `GET /status` | current capture state (poll fallback) |
| `GET /stream` | **SSE** live status (poses, coverage, detection) |
| `GET /preview` | **MJPEG** (`multipart/x-mixed-replace`) composite + overlay |
| `GET /active` | active calibration summary |
| `GET /export` | download active `bay_calib.json` |
| `GET /history` · `POST /activate/{id}` | list past calibrations, re-activate |

Preview + SSE use `StreamingResponse` (the codebase’s existing SSE mechanism).
DB access from the daemon thread uses the established `check_same_thread=False`
request/worker conn pattern (`deps.py`).

## 9. Frontend — Connect-screen "Camera Calibration" card

In `web/frontend/src/pages/ConnectScreen.tsx`, a new card (typed `lib/api.ts`
calls + an SSE hook reusing `useSse`):
- **Inputs:** camera device index, checkerboard cols/rows (inner corners), square
  size (inches or mm), with helper text linking the calibration guide.
- **Live preview:** `<img src="/api/calibration/preview">` (MJPEG) with the
  backend-drawn detected-corner overlay + coverage-grid heat overlay.
- **Status:** good-pose counter, a coverage-grid widget filling in as areas are
  covered, hint line ("cover the corners", "hold steadier", "board out of frame").
- **Controls:** Start / Stop Capture, Run Calibration, result readout (✓ *N poses ·
  reprojection X px* / ✗ recapture), Active calibration + timestamp,
  Re-calibrate, Export, history list with Activate.
- Loading/empty/error states consistent with the other screens.

## 10. Wire-up to the 3D pipeline

When an active calibration exists, `process_video(..., calibration=...)` (and any
future live-swing path) is given `CheckerboardCalibration(active_calib_json)`;
otherwise it falls back to `AssumedGeometryCalibration`. A small helper
`vision/threed/calibration.py::active_calibration(conn)` returns the right
provider. The [calibration guide](../../guides/bay-camera-calibration-guide.md)
gets a short "in the app: open Connect → Camera Calibration → Start" addendum.

## 11. Validation strategy

1. **Synthetic checkerboard closed-loop (automated):** generate a board, project
   it through two known camera matrices into a composite, run `detect_board` +
   `stereo_calibrate`, assert recovered intrinsics/extrinsics ≈ known and
   reprojection error ≈ 0. Proves the math with no hardware.
2. **Mock camera source (automated):** a `FrameSource` replaying fixed frames
   drives `CalibrationSupervisor` (start → accumulate → run) in tests — no device.
3. **Store/API/frontend (automated):** calibration record lifecycle + active
   selection; endpoint contracts; vitest for the card states.
4. **Laptop-webcam smoke test (manual, user-run):** single-camera test mode →
   real device I/O, real-frame checkerboard detection, MJPEG preview, coverage
   map, SSE feedback all exercised live. User has a printed board (measure a
   square in inches → ×25.4; scale doesn’t affect the angle metrics anyway).
5. **Real two-camera bay (later):** full stereo accuracy; coverage-threshold
   tuning against real frames.

## 12. Risks

- **No live camera until the bay** → the device-I/O path validates via the webcam
  smoke test (single-camera) now; full stereo at the bay.
- **Coverage-map thresholds want real frames** → ship sensible defaults; expect a
  tuning pass at the bay (accepted).
- **Daemon-thread DB access** → reuse the proven `check_same_thread=False` pattern
  (the SSE cross-thread sqlite bug is already solved in `deps.py`).
- **MJPEG flakiness** → periodic-JPEG-snapshot fallback if needed.
- **World-frame axes (turn sign/zero)** → the engine sets sane defaults from the
  capture; a few board-flat-on-ground-aligned-to-target poses pin it. Documented
  in the guide; a sign flip in `bay_calib.json` is the escape hatch.
- **One webcam ≠ stereo** → test mode is explicitly for plumbing, not accuracy.

## 13. Consumes / Produces

- **Consumes:** the existing `FrameSource`/`split_views` interface, the
  `CaptureSupervisor`/SSE/deps patterns, `scripts/calibrate_bay_cameras.py` logic
  (promoted), the store + API + Connect-screen conventions.
- **Produces:** `LiveCameraSource`; the checkerboard engine + `CheckerboardCalibration`
  (completing Task 11); the `calibration` table; `/api/calibration/*`; the Connect
  card; an active calibration that lights up the 3D metrics at GolfTEC accuracy.
