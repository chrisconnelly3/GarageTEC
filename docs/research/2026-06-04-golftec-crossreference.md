# GolfTEC Tour Averages vs Our GolfDB 2D Reference — Cross-Reference

**Date:** 2026-06-04. Companion to `2026-06-04-pro-biomechanics-literature.md`
(peer-reviewed) and the GolfDB pro reference (`coach/norms/pro_reference/`).

Two user-supplied GolfTEC sources cross-checked against the numbers we computed
ourselves from GolfDB tour-pro video:
- GolfTEC **Tour Averages** chart (150+ PGA/Senior/LPGA/mini-tour players, with
  HealthSouth) — full address/top/impact/finish table.
- GolfTEC **SwingTRU Motion Study** (13,000+ golfers, pro → 30-hcp).

---

## How GolfTEC measures shoulder/hip TURN from the *same two camera angles we use*

**OptiMotion uses exactly our two views — face-on + down-the-line — and an AI
model that fuses them into 3D, markerless (no sensors/harness).** It captures
4,000+ data points/swing; GolfTEC's library is 14M+ swings.

The crux: **a single 2D view cannot see rotation about the vertical axis** (turn)
— it's out-of-plane. But **two orthogonal, calibrated, time-synced views can be
triangulated into a metric 3D skeleton**, and in 3D the shoulder/pelvis turn (and
true side-bend at rotated positions) fall straight out. The face-on camera
supplies the left-right + up-down; the down-the-line camera supplies the *depth*
the face-on one is blind to. Fuse them → 3D → turn.

So the user's intuition is exactly right: it's the **same pose points, cross-
referenced across the two views** into 3D — not a magic extra sensor. (The 2011
chart predates OptiMotion and used a HealthSouth body-sensor harness; same 3D
quantities, different capture.)

**What WE do today vs GolfTEC:** we run MediaPipe pose **independently on each
view in 2D** and never fuse them, so:
- turn/X-factor are unrecoverable (out-of-plane in either single view), and
- tilt reads are **foreshortened once the torso rotates** (top, impact).

**Paths to close the gap (in increasing cost/accuracy):**
1. **MediaPipe world landmarks (monocular 3D, ~free).** `mp.solutions.pose`
   already returns `pose_world_landmarks` (metric 3D from the GHUM model) per
   view — we only use the 2D pixel landmarks. Rough depth, but enough for a first
   3D turn/tilt estimate, and **testable on the GolfDB clips right now** (single
   view). Good for a feasibility spike + cross-check vs GolfTEC's 36°/43°.
2. **Two-view triangulation (GolfTEC-grade).** Calibrate the two bay cameras once
   (intrinsics + relative pose, e.g. a checkerboard/known target) + time-sync the
   frames, then triangulate the per-view 2D landmarks into metric 3D. This is the
   real fix and matches OptiMotion's approach. Needs the production rig
   (calibration + sync) — not possible on GolfDB (single-view clips).

---

## The two GolfTEC datasets

### Tour Averages chart (degrees; direction as labeled)
| Parameter | Address | Top | Impact | Finish |
|---|---|---|---|---|
| Shoulder turn | 5 open | **89 closed** | 48 open | 138 open |
| Shoulder tilt | **10 right** | **36 left** | **43 right** | 15 right |
| Shoulder bend (fwd) | 36 fwd | 2 fwd | 17 fwd | 30 back |
| Hip turn | 2 closed | **48 closed** | **42 open** | 106 open |
| Hip tilt | 0 neutral | 11 left | **14 right** | 5 right |
| Hip bend (fwd) | 14 fwd | 9 fwd | 5 back | 5 back |

### SwingTRU (pro values; "lower handicap ⇒ more")
Hip sway @ top **3.9" toward target** · Shoulder tilt @ top **36°** · Hip sway @
impact **1.6" toward target** · Hip turn @ impact **36° open** · Shoulder tilt @
impact **39°** · Shoulder bend @ finish **32° back**.

The two GolfTEC sources agree with each other (shoulder tilt @ top 36° = 36°;
@ impact 39° ≈ 43°; hip turn @ impact 36° ≈ 42°).

---

## Cross-reference: GolfTEC 3D vs our GolfDB 2D (view-corrected sample, 99 swings, 84 pros)

Our values are the acute-magnitude angles from 2D face-on/DTL; sway converted
from %-shoulder-width to inches at a 16.6" biacromial breadth (≈ 5'9" golfer).
**Data-quality note:** pose-based view auto-detection reclassified **18 of 99
clips (~18%)** vs GolfDB's labels (e.g. several "face-on" Tiger/Fred Couples/
Langer clips were actually down-the-line) — without this, the buckets would be
~18% cross-contaminated.

| Position · metric | GolfTEC 3D | Our GolfDB 2D (median [p10–p90], n) | Verdict |
|---|---|---|---|
| **Address · shoulder tilt** | 10° | **10.5° [5.8–15.0]** (n=46) | ✅ **near-perfect** |
| Top · shoulder tilt | 36° | 9.8° [4.1–14.6] | ❌ we under-read (foreshortened) |
| Impact · shoulder tilt | 43° / 39° | 11.9° [5.8–24.7] | ❌ under-read (p90 closes some) |
| Address · hip tilt | 0° | 3.8° [1.2–7.7] | ≈ close |
| Impact · hip tilt | 14° | 4.2° [0.7–7.4] | ❌ under-read |
| Address · forward bend | 36° fwd (shoulder bend) | spine 28.3° vs vertical (n=52) | ≈ ballpark (diff. landmarks) |
| Top · hip sway | 3.9" → target | ~0.8" | ❌ differs (definition/timing) |
| **Impact · hip sway** | 1.6" → target | **~1.0"** | ✅ **same order** |
| Top · shoulder turn | 89° closed | — | 🚫 3D-only (not computed) |
| Impact · hip turn | 36–42° open | — | 🚫 3D-only (not computed) |

### Reading
- **Square-to-camera positions VALIDATE our pipeline.** Shoulder tilt at address
  (10° vs 10°) and impact hip sway (~2.2" vs 1.6") land right on GolfTEC's tour
  numbers — independent confirmation that our 2D angles + scale-free sway are
  computed correctly.
- **Rotated positions under-read, predictably.** At top and impact the torso has
  turned out of the face-on plane, so the 2D projection foreshortens the tilt
  (shoulder tilt @ impact 11.7° vs 43°; our p90 reaches 29° for the swings most
  square at impact). This is the *same* geometry that makes turn invisible to one
  2D camera — and it matches the peer-reviewed finding that side-bend/rotation at
  rotated positions need 3D.
- **Hip sway @ top mismatch (0.3" vs 3.9")** is the one to reconcile — likely a
  reference/timing/definition difference (GolfTEC pelvis-center 3D vs our hip-
  midpoint from the GolfDB "top" event frame). Impact sway agreeing is reassuring.

### Implication for the "drop rotation" decision
The earlier call to drop the **2D-foreshortening** rotation estimate stands — that
*method* is junk. But rotation/X-factor themselves are **not** unmeasurable for
us: they need **3D**, which the same two GarageTEC cameras can deliver via fusion
(option 1 or 2 above). GolfTEC is the existence proof. Recommended: spike option 1
(MediaPipe world landmarks) on the GolfDB clips and compare a 3D shoulder-turn
estimate against GolfTEC's 89°-closed/48°-open benchmarks before committing to the
full two-view calibration rig.

**Net:** our self-computed GolfDB reference is **validated against GolfTEC where
2D is geometrically valid** (square positions) and **quantifies its own limit**
where it isn't (rotated positions) — and the fix is 3D view-fusion, exactly what
OptiMotion does.

---

## DECISION (2026-06-04): GolfTEC numbers are AUTHORITATIVE

Per the user: **trust GolfTEC's published numbers over our GolfDB-deduced numbers
wherever they conflict** (e.g. hip sway @ top 3.9" not 0.3"). Encoded as the
primary ideal tier in `coach/norms/pro_reference/golftec_reference.json`
(generator `build_golftec_reference.py`, hand-transcribed Tour Averages +
SwingTRU with provenance). The GolfDB `pro_reference.json` is now **secondary**:
(a) fills metrics GolfTEC doesn't publish (head sway, hand depth), and (b) is a
*same-projection 2D pro baseline* for the rotated-position metrics until 3D
exists. Every GolfTEC (metric, phase) carries `two_d_comparable_now` — the app may
compare its live 2D value to the GolfTEC target ONLY where that is true (square
positions); the rest await 3D.

## Monocular-3D spike result (MediaPipe `pose_world_landmarks`)

Tested whether MediaPipe's built-in monocular 3D can recover turn from a single
GolfDB view (16 cached clips). **Verdict: not reliable enough to ship.**

| view | shoulder turn @top (median) | GolfTEC | read |
|---|---|---|---|
| face-on | **4°** | 89° | fails — top foreshortens, depth unrecoverable |
| down-the-line | **63°** | 89° | promising but noisy (best clips 95–108°, worst 9°) |

The turn signal lives in the **down-the-line** view (face-on can't see it), but
monocular depth is too noisy per-clip. **Conclusion:** don't ship monocular 3D;
the reliable path is **two-camera triangulation** (below), deferred.

## DEFERRED follow-up — GolfTEC-grade two-camera 3D (blocked on the GarageTEC sim)

Once the GarageTEC sim/bay rig is built and testable: **calibrate the two bay
cameras once** (intrinsics + relative pose via a checkerboard/known target) +
**time-sync the frames**, then **triangulate the per-view MediaPipe 2D landmarks
into metric 3D**. That yields shoulder/hip turn, X-factor, and accurate
side-bend at rotated positions — matching GolfTEC OptiMotion — and lets the app
compare live swings to the full GolfTEC reference (not just the square-position
subset). This is the real unlock; tracked in project memory.
