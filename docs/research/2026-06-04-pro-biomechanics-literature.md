# Pro / Skilled-Golfer Biomechanics — Literature Reference (Phase 4, thread B)

**Date:** 2026-06-04
**Method:** deep-research workflow (fan-out web search → fetch 22 sources → extract
96 claims → adversarial 3-vote verification of top 25 → synthesize). 23/25 claims
confirmed, 2 killed. 105 agents.
**Purpose:** cross-check the tour-pro reference we compute ourselves from GolfDB
2D video (thread A), and supply ranges for metrics 2D video cannot capture.

---

## ⚠️ The central finding (this reframes what 2D can do)

**Of the 10 requested metrics, only ~2 are genuinely measurable from 2D FACE-ON
video:** secondary spine tilt (side-bend) at impact, and *possibly* hip lateral
tilt at impact. **Spine/forward bend is 2D-measurable only from DOWN-THE-LINE,
not face-on.** Every axial-rotation metric — shoulder turn, hip turn, **X-factor,
X-factor stretch** — is *out-of-plane* for a face-on camera and **requires 3D
mocap**. Published 2D-projected rotation values are inflated and method-dependent,
so they are **not valid cross-check targets** for a 3D quantity.

> This independently confirms our Phase-4 decision to treat the foreshortening
> rotation metrics (`shoulder_turn_deg`, `hip_turn_deg`) as junk, and to keep the
> pro reference to angles (tilt, spine) + scale-free sway.

A second foundational caveat: **there is NO standardized X-factor computation** —
the common methods differ significantly (P<0.05) and are not interchangeable
across studies (Brown, Selbie & Wallace 2013). Never treat a single X-factor
number as canonical; report a band.

---

## Per-metric skilled-golfer reference values (verified)

Gold-standard rotational source = **Meister et al. 2011** (10 *elite male pros*,
8-camera optical mocap, 5-iron). Side-bend driver values = **Joyce et al. 2013**
(15 low-hcp amateurs, Vicon). Both 3D.

| # | Metric (position) | Skilled value | Population / n | Method | 2D-viable? |
|---|---|---|---|---|---|
| 1 | **Shoulder side-bend / S-factor @ impact** | **25 ± 3°** (peak 48 ± 4°) | 10 elite male pros | 3D optical mocap, 5-iron | **face-on (projection, attenuated)** |
| 1b| Trunk lateral bend @ impact (driver) | −31.8 ± 7.2° (upper), −11.7 ± 4.7° (lower) | 15 low-hcp am | 3D Vicon | face-on (proj.) |
| 2 | **Hip/pelvis lateral tilt / O-factor @ impact** | **12 ± 3°** (peak 16 ± 4°) | 10 elite male pros | 3D optical mocap | face-on (proj., *least consistent* param, Cv 23.9%) |
| 2b| Hip tilt @ address | qualitative only ("lead hip slightly elevated", O-factor *theory*) | — | — | thin |
| 3 | **Shoulder/thorax axial turn @ top** | ~99 ± 6° (peak upper-torso, pros); ~60° trunk (low-hcp) | 10 pros / 15 am | 3D | ❌ **3D-only** |
| 4 | **Hip/pelvis axial turn (peak)** | ~46 ± 6° (pros; NS across efforts) | 10 pros | 3D | ❌ **3D-only** |
| 5 | **X-factor @ top** | **~42–48°** (TPI tour avg ~42; Cheetham elite mean ~48); **peak/stretch ~56 ± 4°**; @ impact ~33 ± 6° | 10 pros + industry | 3D | ❌ **3D-only**, *not standardized* |
| 5b| **X-factor at top does NOT discriminate skill** — the **stretch** in early downswing does (skilled +19% vs +13%, interaction p=.02) | — | Cheetham 2001 (n=10 vs 9) | 3D EM mocap | ❌ 3D-velocity-timing |
| 6 | **Spine / forward bend @ address** | **45–60° vs horizontal**; **STABILITY (not magnitude) marks skill** (SD–score r=0.80, p<0.01) | 27 university golfers (not pros) | **2D markerless, sagittal / DTL** | **down-the-line only** |
| 7 | **Early extension** | **67% of amateurs vs ~0% of pros**; no peer-reviewed mm/deg threshold | TPI screen >90,000 (industry) | TPI screen | practitioner stat only |
| 8 | **Hip sway / pelvis lateral translation** | **— no citable skilled value found —** | — | — | **THIN/ABSENT** |
| 9 | **Head sway / lateral head movement** | **— no citable skilled value found —** | — | — | **THIN/ABSENT** |
| 10| **Hand depth / hand path / lead-arm** | **— no citable skilled value found —** | — | — | **THIN/ABSENT** |

**Sex must be controlled** (Horan et al. 2010, 19 M + 19 F skilled): at impact
males show greater trail-side thorax/pelvis lateral tilt and less left axial
rotation than females; *male optimal characteristics should not be generalized to
females.* Our GolfDB reference mixes both sexes → a known limitation.

---

## Cross-check vs our GolfDB-computed pro reference (thread A)

Our 2D values are **projections**, so they read **lower** than the 3D mocap
"true" side-bend/tilt — as expected (a face-on camera sees only the in-plane
component). Directions and trends match; absolute magnitudes are attenuated.

| Metric @ phase | Literature (3D) | Our GolfDB 2D (sample, median [p10–p90]) | Read |
|---|---|---|---|
| Shoulder tilt @ impact | 25 ± 3° (S-factor, 3D) | ~12.7° [8.4–31.1] | 2D projection attenuates; p90 overlaps 3D |
| Shoulder tilt @ address | thin / qualitative | ~11.2° [6.6–16.6] | fills a gap; ≈ CaddieSet population band |
| Hip tilt @ impact | 12 ± 3° (O-factor, 3D) | ~4.6° [1.0–7.8] | attenuated projection; same order |
| Spine angle @ address (vs **vertical**) | 45–60° vs horizontal = **30–45° vs vertical** | ~29.6° [19.6–35.6] | overlaps lower end; **track consistency too** |
| Shoulder/hip turn, X-factor | 3D-only | (not computed — junk in 2D) | ✅ literature confirms drop |
| Hip / head sway (% shoulder width) | **none published** | hip ~0.17 @ impact, head ~0.03 | **our numbers are the best available** |

**Implications for the build:**
1. **Keep the exact-angle pro tier** (`shoulder_tilt`, `hip_tilt`, `spine_angle`)
   — literature-backed and 2D-viable. Note our values are *projected* (attenuated
   vs 3D); compare amateur-to-pro within our own 2D definition, not vs 3D numbers.
2. **Spine angle: also reward CONSISTENCY**, not just hitting a band (Yamamoto
   2023: stability discriminates skill, magnitude does not). And spine is
   **DTL-only** — never expect it from a face-on clip.
3. **Drop rotation / X-factor from the 2D pro reference** (confirmed 3D-only). If
   ever wanted, they need a 3D capture path; cite the ~42–48° @ top band and the
   "stretch, not top, discriminates skill" caveat.
4. **Sway / head / hand-depth: our GolfDB reference is the only quantitative
   skilled-golfer source** — there is no literature to cross-check it against.
   Treat as provisional but novel; this is a genuine contribution, not a gap.
5. **Early extension:** binary screen (present/absent), pros ~0%. No magnitude
   threshold exists → our early_extension band should be framed as "near-zero for
   pros," not a precise degree target.
6. **Control for sex** where possible (or at least flag the mixed-sex limitation).

---

## Killed claims (failed verification — do NOT use)

- ✗ "Upper-torso axial turn at top ≈ 30°" (IMU study) — refuted 0-3; that study
  plotted amateurs over an averaged pro curve and ran no kinematic stats.
- ✗ "Tour pros average ~5° of X-factor stretch" — refuted 0-3 (misreads TPI;
  skilled stretch is ~19% gain, not 5°).

## Open questions (genuine gaps)

1. Citable skilled hip-sway / head-sway values in cm or % stance — none found
   (may live in TPI/AMM3D internal data or pressure-plate literature).
2. Numeric address-position lateral-tilt values for skilled golfers (beyond
   "lead hip slightly elevated" theory).
3. A peer-reviewed mm/deg early-extension threshold separating skilled vs amateur.
4. **A face-on-2D-vs-3D validation study** (impact side-bend & hip tilt 2D
   estimate vs simultaneous mocap) — would calibrate the projection attenuation
   in our pipeline. *This is the highest-value follow-up for our cross-check.*

---

## Sources (primary unless noted)

- **Meister et al. 2011**, *Rotational biomechanics of the elite golf swing*, J
  Appl Biomech 27:242–251. https://pubmed.ncbi.nlm.nih.gov/21844613/
- **Joyce et al. 2013**, *Three-dimensional trunk kinematics in golf*, Sports
  Biomech 12:108–120. researchgate.net/publication/253646842
- **Cheetham et al. 2001**, *Stretching the X-Factor*.
  philcheetham.com/wp-content/uploads/2011/11/Stretching-the-X-Factor-Paper.pdf
- **Horan et al. 2010**, *Thorax and pelvis kinematics… male and female skilled
  golfers*, J Biomech 43(8):1456–1462. sciencedirect.com/science/article/abs/pii/S0021929010000801
- **Brown, Selbie & Wallace 2013**, *The X-Factor: evaluation of common methods*,
  J Sports Sci. researchgate.net/publication/235883466
- **Yamamoto et al. 2023**, *Front Sports Act Living* 5:1272038 (2D markerless
  posture, consistency vs skill). frontiersin.org/.../fspor.2023.1272038/full
- **Frontiers 2022** 5:986281 — Swing Performance Index, 3D rotational-velocity
  timing separates pros (AUC 0.97). frontiersin.org/.../fspor.2022.986281/full
- IMU validation (18 pro + 18 am), PMC10611231 — *no usable pro angle table*.
- TPI: X-factor vs stretch (mytpi.com); early extension (mytpi.com) — *industry
  stats, no published methodology*.
- K-Motion, GEARS, AMM 6DOF (Cheetham) — industry/secondary.
