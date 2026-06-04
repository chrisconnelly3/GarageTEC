# Phase 4 research — 7 golf-swing repos analyzed (code-level)

Goal: fill 3 gaps — **(1) swing segmentation** (over-split: top-of-backswing pause splits one swing into 4), **(2) norms / ideal ranges**, **(3) benchmarking**. Each repo was cloned and its source read (not just README).

## Verdict per repo

| Repo | License | Segmentation | Norms | Benchmarking | Net |
|---|---|---|---|---|---|
| **damilab/CaddieSet** | MIT ✓ | None (data only) | **Medium ✓** | Low–Med | **Norms dataset** |
| ryanboscobanze/GolfPosePro | MIT ✓ | Low (same bug) | None | Low (concept) | ~ffmpeg slow-mo snippet only |
| MingHanLee/GolfPose | **none ✗** | None | None | None | Dead end (3D pose, GPU, no license) |
| splenwilz/golf_swing_analysis | **none ✗** | None | None | None | Dead end (mocab notebook, unrun) |
| **Strojove-uceni/23206-…** | **none ✗** | Low (→ GolfDB) | Med (uncited bands) | **Med–High (method)** | **Ideas + GolfDB signpost** |
| **Robin-Hood-zjw/golf_swing** | MIT ✓ (data 3rd-party) | Low (model) / **High (data)** | None | None | **Ships GolfDB labels** |
| HeleenaRobert/golf-swing-analysis | MIT ✓ | None | None | None | Dead end (120-line demo) |

## Gap 1 — Segmentation: the real answer is GolfDB / SwingNet
- Strojove-uceni, Robin-Hood-zjw, and splenwilz all lean on **GolfDB / SwingNet** (McNally et al., CVPR-W 2019, `github.com/wmcnally/golfdb`): an ML event detector (MobileNetV2 + bi-LSTM) trained on **1,400 labeled swings with exactly our 8 events**. A temporal model enforces one-frame-per-event ordering across the whole sequence, so the top pause can't split a swing. This is the credible fix — not in our list of 7, but where they all point.
- **Robin-Hood-zjw/golf_swing ships the GolfDB labels** (`Algorithm/data/GolfDB.csv/.pkl`): 1,400 clips × `events` frame-index arrays (8 events), with `view` (DTL/face-on), `club`, `bbox`. Usable to train/validate our own segmenter. (GolfDB data is 3rd-party academic/YouTube — fine for internal train/validate; check license before product redistribution.)
- **Cheap near-term heuristic fix (from Strojove-uceni's idea):** segment on the **continuous wrist/hand position trajectory** (one big excursion-and-return = one swing), NOT a motion-energy "burst-between-stillness" signal. The top pause is just a turning point on a continuous curve, not a gap — so it's structurally immune to our over-split. No new deps; fits our MediaPipe stack now.

## Gap 2 — Norms: CaddieSet is the find
- **`damilab/CaddieSet`** (MIT): `data/CaddieSet.csv` = 1,757 real shots × per-phase body-mechanics features, with **events 0–7 = our 8 phases**. Columns like `0-SHOULDER-ANGLE`, `4-SPINE-ANGLE`, `2-LEFT-ARM-ANGLE`, `STANCE-RATIO`, `HEAD-LOC`, `WEIGHT-SHIFT`. Use as an **empirical percentile reference** (p10/median/p90) per phase — after cleaning junk (`inf`, exact `0`/`180` clamps, extreme outliers). Plus the README (lines 28–49) is a ready **catalog of ~20 pose-metric definitions**. Caveat: mixed-skill *population* stats, not validated good/bad thresholds.
- **Strojove-uceni** gives concrete (but **uncited, pixel-based, internally inconsistent**) "good" bands as a scaffold of *which* checks to implement: lead-arm 165–180° straight / 130–150° folded at top; lead-knee 165–180° at impact; spine-line ~165–180°; head movement small; shoulder-over-lead-foot at impact. Replace the numbers with sourced ones.
- Still need proper cited literature (TPI / 3D biomechanics: X-factor, pelvis-thorax separation, etc.) for authoritative bands → feed the AI-coach `norms.json` with `source` + `confidence` per our spec.

## Gap 3 — Benchmarking: borrow the method, not code
- **Standard method (all point here):** **DTW over phase-aligned joint-angle / landmark trajectories** — align student-at-phase to reference-at-phase, score distance. GolfPosePro shows only the *concept* (phase-anchored frame compare); implement the math ourselves.
- **Strojove-uceni method nuggets:** (a) run metrics over a **corpus of known-good/pro swings and tune thresholds so pros rarely flag** (cheap threshold validation + pose-backend choice); (b) GolfDB **PCE tolerance metric** (`2*frames/30fps`) to score phase-detection accuracy.
- **CaddieSet** pairs each swing with ball outcome → derive feature→outcome **weights** (which metrics matter most: e.g. top-of-backswing lead-arm straightness correlated with carry r≈+0.38) to prioritize coaching, not weight all metrics equally.

## Recommended plan (uses the findings)
1. **Segmentation (now):** redesign swing-detect to the **continuous wrist/hand-position-trajectory** approach (immune to the pause) + merge bursts <~1s → fixes the over-split with no new deps. Validate on the real `golf swing.MOV`. (Upgrade path later: GolfDB/SwingNet ML event detector for robust 8-phase, validated on the GolfDB labels.)
2. **Norms:** clean CaddieSet.csv → per-phase percentile bands + the metric-definition catalog; layer cited literature; populate `coach/norms/norms.json` with sources + confidence.
3. **Benchmarking:** DTW over phase-aligned joint-angle series vs the player's own good swings (+ optional reference); adopt the pro-corpus threshold-tuning method.

**Dead ends (skip):** MingHanLee/GolfPose, splenwilz, HeleenaRobert (no value); GolfPosePro (only an ffmpeg slow-mo snippet). **No-license repos** (GolfPose, splenwilz, Strojove-uceni) = ideas/numbers only, reimplement — do not copy code.
