# Bay Verification Checklist

**Purpose:** Things that are implemented on a best-guess basis and MUST be verified
with the real physical bay (real cameras + real pose data), because they can't be
fully validated from seed/synthetic data. Run through this once the hardware is set
up and you tell the assistant "the bay is up and running."

---

## ⚠️ HIGH PRIORITY — Sway sign convention (directional benchmarking)

**Context:** Head/hip sway are benchmarked **directionally** — the green/yellow/red
light cares *which way* you move, not just how much (e.g. head drifting *behind the
ball* at the top is good/green; sliding *toward the target* is a fault/red). This is
the coaching-correct model, but it depends on our measured value carrying the right
**sign** for "good direction," which we could only set from our best current
understanding of the metric code, not real footage.

**Verify, on real swings in the bay:**
1. **Head sway @ top** reads GREEN for a normal, behind-the-ball backswing load
   (NOT red). If a good swing shows red, the sign for `head_sway_in` is inverted —
   flip its target sign in `coach/metric_thresholds.py` / `supplementary_reference.json`.
2. **Hip sway @ top/impact** rewards the proper lateral shift toward the target on
   the downswing (green near the tour amount), and flags over-sliding / hanging back.
3. **Left-handed players:** a lefty mirrors everything, so the "good" sway direction
   flips. Confirm a good LH swing scores green too. If LH is inverted vs RH, the sway
   metric (`metrics/defs/sway.py`) likely needs to normalize sign by handedness.

**Where it lives:** `coach/metric_thresholds.py` (sway directional mode + signs),
`coach/norms/pro_reference/supplementary_reference.json` (head_sway target sign),
`coach/golftec.py` (hip_sway targets), `metrics/defs/sway.py` (measured sign).

---

## Other items to validate with real data/hardware

- **3D camera intrinsics:** confirm checkerboard-calibrated 3D metrics (turns, X-Factor,
  3D tilts) read sensibly vs the GolfTEC tour numbers once calibrated. The assumed-geometry
  (uncalibrated) fallback is approximate by design.
- **Live swing capture:** first real run with two USB cameras — confirm each shot's swing
  video records, processes, and pairs to the R50 shot (the "vs Tour Pro" body cards appear
  a few seconds after the ball data). Watch for any swings that silently don't appear.
- **Two-camera 3D skew:** unsynced free-running USB cameras introduce some 3D error on fast
  motion; sanity-check 3D metrics against feel and consider the sync caveat in the 3D spec.
- **Replay → phase sync:** confirm the Live phase-jumper seeks the real annotated video and
  the body cards update across address → top → impact as expected.
- **Skeleton (exoskeleton) overlay alignment:** the toggle draws a per-frame pose skeleton
  over the swing video from a `<video>.pose.json` sidecar (normalized 0..1 coords). It was
  built/verified against the rotated two-view demo clip (`extract_pose.py` splits the frame
  into left/right halves and runs MediaPipe per half, mapping x into [0,0.5]/[0.5,1]).
  Confirm with the REAL two-camera composite: (a) the skeleton lands on the golfer in BOTH
  views, (b) the left/right split matches the real composite layout (not stacked/rotated
  differently), and (c) the overlay stays aligned through object-contain letterboxing at the
  bay's actual aspect ratio. The real capture pipeline should emit the same sidecar shape.
- **Stepper phase times:** Live position-stepper times come from the capture pipeline's
  detected moments on real swings (the demo's were hand-calibrated to `smooth_swing.mov`).
  Confirm the highlighted step tracks the real video through all 8 positions. Note:
  `extract_pose.py`'s built-in `detect_phases` heuristic is demo-only and unreliable
  (top-of-backswing vs finish ambiguity) — do not rely on it for real captures.

---

## ⚠️ RTMPose backend cutover (do this when the GPU box + bay are ready)

We switched the pose model to **RTMPose** (top-down, via `rtmlib` + ONNX Runtime) because
MediaPipe BlazePose tracked the arms poorly under golf occlusion. The skeleton OVERLAY
already runs RTMPose; the metric pipeline still defaults to MediaPipe (`vision/constants.py`
`POSE_BACKEND = "mediapipe"`) so CPU/CI stay fast. Finish the cutover in the real bay:

1. **GPU + flip the backend.** Install `onnxruntime-gpu` (CUDA) on the bay PC, then set
   `POSE_BACKEND = "rtmpose"` (or pass `pose_backend="rtmpose"` to `process_video`). A cheap
   NVIDIA card suffices — **GTX 1050 Ti 4 GB minimum, GTX 1060 6 GB comfortable** (RTMPose
   needs ~1–2 GB VRAM; ~hundreds of fps → live overlay). On CPU it's ~12 fps (skeleton ready
   ~10–15 s after a shot); the GPU makes it instant + live.
2. **Calibrate the two bay cameras.** Until there's a real checkerboard calibration, 3D
   metrics fall back to "assumed geometry" and are **physically wrong** — verified by running
   the real pipeline on the uncalibrated demo clip, which produced absurd values (175° spine
   tilt, 17″ sway). Only trust metric numbers (and tune the stoplight) from CALIBRATED bay
   swings, NOT from arbitrary clips.
3. **Tune the stoplight thresholds** (`coach/metric_thresholds.py`) on real calibrated swings
   — the current thresholds were set against synthetic demo data.
4. **Verify the model integrity before shipping.** RTMPose/YOLOX ONNX were fetched from a
   community mirror for the prototype (`vision/pose_rtm.py` logs each file's SHA-256). For
   production, obtain the **official OpenMMLab** file and verify its SHA-256 matches, or
   pin the verified hash in `_SOURCES`. Current (unverified) hashes are logged at load time.
5. **Top-of-swing arm occlusion → fix with MULTI-VIEW (the chosen path).** A SINGLE camera
   cannot reliably resolve the overlapping hands during the backswing and at the top — the
   skeleton splits the wrists (one hand stays correct, the other jumps to the hip). Verified
   to be a fundamental single-view 2D limitation, NOT a model gap: RTMPose-m and ViTPose-s
   both fail it (each drops a different hand), and a confidence-based "snap the hands
   together" patch was tested and made the TOP worse (dragged the good hand down to the bad
   one). RTMPose is correct at address/downswing/impact/finish; only the most-occluded
   backswing/top split. The proper fix uses BOTH bay cameras: triangulate the wrists from the
   two calibrated views (each sees a different occlusion) and reproject the fused 3D back into
   each view to drive the overlay. So once calibration exists (step 2), have the overlay read
   the reprojected 3D landmarks (the metric pipeline already triangulates) instead of raw
   per-view 2D. Until then, expect the top-of-swing arms to look imperfect on single-view
   playback — this is known and accepted, not a regression.
6. **OpenFlight enrichment: which shot wins a same-speed record.** Ball speed is the ONLY
   correlation key between OpenFlight's two channels (the OpenConnect wire shot and its
   Socket.IO enrichment record), so two shots with the same rounded ball speed inside the
   5 s window are indistinguishable to a record. Two claim paths exist and they use
   different heuristics: the pre-INSERT claim in `handle_message` attaches a buffered record
   to the CURRENT shot, while the late/re-poll path (`_attach_to_recent_shot`) attaches it to
   the OLDEST un-enriched same-speed shot (FIFO). FIFO is the deliberate choice: both channels
   emit in shot order, so a merely delayed enrichment stream still pairs correctly. The known
   reachable case is a same-speed shot within 5 s that is still un-enriched when the next
   shot's record lands mid-INSERT — the earlier shot takes it and the later one gets none.
   **In the bay:** hit deliberate back-to-back shots at near-identical ball speed and confirm
   the "est." markers and per-field provenance land on the right shots. If they do not, the
   fix is a stronger correlation key (e.g. have OpenFlight's `ShotNumber` carried on both
   channels) rather than tuning the window.
