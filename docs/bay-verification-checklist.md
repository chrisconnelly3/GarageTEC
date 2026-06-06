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
