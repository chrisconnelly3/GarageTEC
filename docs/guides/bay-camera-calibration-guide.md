# GarageTEC Bay Camera Calibration — Step-by-Step Guide

**Created:** 2026-06-04 · **For:** the one-time calibration you run AFTER the
GarageTEC bay/sim is built, to unlock the 3D metrics (shoulder/hip turn,
X-factor, accurate side-bend) that match GolfTEC's tour numbers.
**You need zero prior knowledge — this explains everything from scratch.**

Related: `docs/superpowers/specs/2026-06-04-two-camera-3d-design.md` (§3),
`docs/superpowers/plans/2026-06-04-two-camera-3d.md` (Task 11),
`scripts/calibrate_bay_cameras.py` (the script you'll run).

---

## 1. What "calibration" is and why you do it (plain English)

To turn the two camera views into real 3D body angles, the software needs to know
two things about your exact camera setup:

1. **Each camera's "lens fingerprint"** (called *intrinsics*) — its zoom/focal
   length, where the exact center of the image is, and how much its lens bends
   straight lines near the edges (distortion). Every camera/lens is slightly
   different.
2. **Where the two cameras sit relative to each other** (called *extrinsics*) —
   the exact distance and angle between the face-on camera and the down-the-line
   camera.

You can't just type these in — you *measure* them by showing both cameras a
known, precise pattern (a checkerboard) from many angles and letting the software
work backwards from how the pattern looks. That's all calibration is: **showing
the cameras a ruler-with-a-known-pattern so they can figure out their own
geometry.**

Once measured, the software saves it to a file (`bay_calib.json`) and uses it
forever — **until a camera gets bumped or moved**, at which point you redo this.

---

## 2. Materials you need (cheap / printable)

| Item | Detail | Where to get |
|---|---|---|
| **A checkerboard pattern** | A flat black-and-white grid of squares, all the same size. The standard is **10 columns × 7 rows of squares** (which gives **9 × 6 *inner corners*** — that's the number the software counts). | Print it (below) or buy a "camera calibration checkerboard" / "OpenCV checkerboard" online (~$15–40 for a rigid one). |
| **A rigid, FLAT backing** | The pattern must be perfectly flat and not bend. | Foam board, a clipboard, a piece of acrylic/MDF, or a hardback book cover. Buy-it boards are already rigid. |
| **A ruler or calipers** | To measure your printed square size precisely. | Any ruler with mm markings; calipers are better. |
| **Good even lighting** | No glare/reflection on the board, no harsh shadows across it. | Your bay's normal lighting is usually fine; avoid a single spotlight glaring off the board. |
| **The two bay cameras, already mounted and FIXED** | Both recording the synced side-by-side composite (the same feed the app uses). | Your finished GarageTEC bay. |

### Printing the checkerboard (free option)
1. Search "OpenCV checkerboard 9x6 pdf" (or "10x7 squares calibration checkerboard
   PDF") and print one at **100% scale / "Actual size"** (turn OFF "fit to page" —
   that resizes it and ruins the measurement).
2. Glue/tape it **flat** onto your rigid backing. No bubbles, no warping.
3. **Measure one square's side with your ruler** (e.g. it might come out 24mm, not
   exactly 25mm — printers aren't exact). **Write this number down** — you'll pass
   it to the script as `--square-mm`. Getting this right is what makes your 3D
   numbers metrically correct.

> A bigger board is easier for the cameras to see across the bay. If your squares
> end up tiny in the camera view, print larger squares (e.g. 30–40mm) on a bigger
> sheet.

---

## 3. The capture: show the board to both cameras

**Goal:** record a short clip (or grab frames) where the checkerboard is clearly
visible **in BOTH camera views at the same time**, held in many different
positions and tilts. ~20–40 good frames is plenty.

**Before you start — the golden rule:** once you begin, **the cameras must not
move at all** (not during capture, not after). If a camera gets bumped, start
over. Calibration measures where the cameras are; if they move, the measurement
is wrong.

**Step by step:**
1. Make sure both cameras are running and producing the **synced side-by-side
   composite** (the same feed GarageTEC records — left half = down-the-line,
   right half = face-on). Start recording.
2. Stand in the hitting area holding the board facing roughly toward the cameras.
3. **Slowly** move the board through lots of variety — hold each pose ~1 second so
   it's sharp (not motion-blurred):
   - **Positions:** center, left, right, high, low, near the cameras, far away —
     cover the whole area where a golfer stands.
   - **Tilts:** flat-on, then tilted left/right, tilted top-toward/away,
     and rotated a bit. Variety of angles is what makes calibration accurate.
   - Keep the **entire** board inside **both** views each time (if half the board
     leaves one camera's frame, that pose is unusable).
4. Aim for **at least 20** clearly-visible, in-focus, full-board poses spread
   across the area. More is better; blurry or half-cut poses are ignored.
5. Stop recording. **Do not move the cameras** — you may want to recapture if the
   result is poor, and the golfer will be filmed with these same fixed cameras.

**Extract frames:** turn your capture into PNG images (one folder, e.g.
`calib_frames/`). If you recorded a video, extract ~2 frames/second:
```
ffmpeg -i your_calibration_clip.mp4 -vf fps=2 calib_frames/frame_%03d.png
```
Each PNG must be the **full composite** (both halves side by side) — the script
splits them itself.

---

## 4. Run the calibration script

From the repo root, run:

```
python scripts/calibrate_bay_cameras.py calib_frames `
  --cols 9 --rows 6 --square-mm 24 --split 0.5 --out bay_calib.json
```

Replace the values with **yours**:
- `calib_frames` — the folder of PNGs you extracted.
- `--cols 9 --rows 6` — the number of **inner corners** (for a 10×7-*square* board
  that's 9×6; in general it's *squares minus one* in each direction).
- `--square-mm 24` — the square size **you measured** in step 2 (millimeters).
- `--split 0.5` — where the composite splits into the two views (0.5 = down the
  middle; matches the app's default).
- `--out bay_calib.json` — the output file.

**What you'll see:** it prints how many checkerboard pairs it found and used. You
want **at least 8**, ideally **20+**. If it says it found too few, you need more
good poses (recapture with more variety / better focus / fuller board).

The result is **`bay_calib.json`** — that's the prize. Keep it with the project.

---

## 5. Verify it worked

1. **Pair count:** the script needed ≥8 pairs (more = better). If it errored with
   "only N usable pairs; need >= 8", recapture with more clearly-visible poses.
2. **Sanity-check the 3D numbers** (this is the real test): point the pipeline at
   `bay_calib.json` and run a known-good swing — a tour-quality swing should show
   **shoulder turn ≈ 85–90° at the top** and **hip turn ≈ 45–50°** (GolfTEC tour
   averages are 89° / 48°). If turn comes out wildly off (e.g. 10°, or 200°),
   something's off — see troubleshooting.

   The dev sanity script for this is `scripts/validate_3d_smooth_swing.py` (point
   it at a real bay swing instead of smooth_swing.mov, and construct a
   `CheckerboardCalibration("bay_calib.json")` instead of the approximate
   provider — see plan Task 11 step 6).

3. **Turn sign/zero looks flipped?** The calibration's "world axes" (which way is
   *up*, which way is *toward the target*) are inferred from how you held the
   board. If turn directions read backwards, the fix is a sign flip in the
   `up` / `target_line` / `depth` lines of `bay_calib.json` (the plan Task 11
   notes this). Easiest prevention: during capture, include a few poses with the
   board laid **flat on the ground aligned down the target line**, so "ground" and
   "target line" are unambiguous.

---

## 6. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| "only N usable pairs; need >= 8" | Board too small/blurry/half-out-of-frame in one view | Recapture: bigger/closer board, hold each pose still, keep the WHOLE board in BOTH views |
| Numbers metrically off (sizes wrong) | Wrong `--square-mm` | Re-measure a printed square precisely; printers don't print exact sizes |
| Corners not detected | Glare/reflection on the board, or board not flat | Diffuse lighting, kill reflections, flatten the board |
| Turn directions reversed | World-axis convention | Flip the relevant sign in `bay_calib.json` (`up`/`target_line`), or include ground-aligned board poses |
| Everything was fine, now it's wrong | A camera got bumped/moved | **Recalibrate** — fixed cameras are mandatory |
| `--cols/--rows` mismatch | Counted squares instead of inner corners | Inner corners = squares − 1 in each direction (10×7 squares → 9×6) |

---

## 7. One-paragraph summary (for when you've done it once)

Print a 9×6-inner-corner checkerboard, glue it flat to a rigid board, measure a
square in mm. With both bay cameras fixed and recording the synced composite,
hold the board through ~20–40 varied positions/tilts (whole board visible in both
views, held still). Extract the frames to PNGs, run
`scripts/calibrate_bay_cameras.py <frames> --cols 9 --rows 6 --square-mm <measured>
--split 0.5 --out bay_calib.json`, confirm ≥20 pairs used, then verify a known-good
swing shows ~89°/48° shoulder/hip turn. Never move the cameras afterward.

## In the app (the normal way)

You don't need the command line. In the app: **Connect → Camera Calibration →
Start Capture**, wave the board through the bay (watch the live preview + coverage
map fill in), then **Run Calibration**. It saves and activates automatically; the
3D metrics use it immediately. **Export** downloads `bay_calib.json` as a backup.
