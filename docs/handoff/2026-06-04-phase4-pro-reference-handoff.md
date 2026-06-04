# GarageTEC — Handoff: Phase 4 Pro-Reference + Benchmarking

> ## ✅ UPDATE 2026-06-04 (session 2): A + B BOTH DONE
> - **B (deep literature research) — DONE.** Cited, adversarially-verified report:
>   `docs/research/2026-06-04-pro-biomechanics-literature.md`. Headline: of the 10
>   metrics, only secondary spine tilt @ impact (and maybe hip tilt @ impact) are
>   2D-face-on-viable; forward bend is DTL-only; **all axial rotation/X-factor is
>   3D-only** (confirms dropping the 2D-foreshortening rotation metric). Sway/head/
>   hand-depth have **no published skilled-golfer norms** → our GolfDB numbers fill
>   that gap. Control for sex.
> - **A (GolfDB pro reference) — BUILT + RUN.** Pipeline `coach/norms/pro_reference/`
>   (`manifest`/`extract`/`build`/`aggregate` + SOURCE.md), 14 tests. Generated
>   `coach/norms/pro_reference/pro_reference.json` from **99 swings / 84 pros**
>   (50/view sample; full set = 1034 swings is one `build.py` run away). EXACT
>   angle metrics `shoulder_tilt_deg`/`hip_tilt_deg`/`spine_angle_deg` = `high`;
>   scale-free sway = `provisional`. Two bugs found+fixed: ±180° tilt wrap → acute-
>   magnitude fold (aggregate); **~18% GolfDB view mislabels** → pose-based view
>   auto-detection (extract.detect_view).
> - **GolfTEC cross-check — DONE.** `docs/research/2026-06-04-golftec-crossreference.md`.
>   Our 2D matches GolfTEC tour averages **at address** (shoulder tilt 10.5° vs 10°;
>   impact hip sway ~1.0" vs 1.6") and **under-reads at top/impact** (2D
>   foreshortening once the torso rotates). **OptiMotion = our SAME two cameras
>   (face-on + DTL) fused into 3D by AI, markerless** — that fusion is how they get
>   turn/X-factor we can't from independent 2D views.
> - **NEW DIRECTION (the real unlock): 3D.** To match GolfTEC on turn/X-factor and
>   on tilt-at-rotated-positions we must go 3D. Two paths: (1) cheap spike —
>   MediaPipe already returns `pose_world_landmarks` (monocular 3D) we don't use,
>   testable on GolfDB clips now; (2) GolfTEC-grade — calibrate + time-sync the two
>   bay cameras, triangulate the 2D landmarks to metric 3D. **OPEN/OFFERED:** run
>   the option-1 MediaPipe-3D turn spike on GolfDB and compare to GolfTEC 89°-closed
>   / 48°-open before any calibration work.
> - **NOT committed yet** (awaiting user go-ahead): new files under
>   `coach/norms/pro_reference/`, `coach/tests/test_pro_reference.py`, the two
>   `docs/research/` docs, `.gitignore` (+`.proref_work/`). `.proref_work/` (CC
>   BY-NC GolfDB clone + videos) is gitignored — never commit it.
>
> Remaining original plan below (benchmarking build + UI) is unchanged.

---

**Purpose:** Continue the pro-reference + benchmarking work in a FRESH session (this one is near context max). The auto-memory (`project_garagetec_plan.md`) loads the full project history; this doc adds the active Phase-4 context + the exact next steps.

---

## ▶ Resume prompt (run this in the new session)

> go with option #1 (A + B, plus mining CaddieSet's good-golfer subset) and maybe introduce using the 'good' golfer data from CaddieSet if you think that would be helpful too... but ideally we can get the pro-level data we need from GolfDB
>
> (Do the deep literature research in THIS new session — it was deferred from the prior one. Read `docs/handoff/2026-06-04-phase4-pro-reference-handoff.md` first.)

---

## Project state (all built, on `main`, pushed to github.com/chrisconnelly3/GarageTEC)
A complete, single, touch-first golf swing-analysis app. Packages: `store catcher vision metrics sync coach web`. R50 capture (GSPro Open Connect) → pose (MediaPipe) → 8-phase swing-chop → 9 body metrics → swing↔shot sync → AI coach (pluggable LLM, default cloud Claude) → unified FastAPI+React dashboard (MagicPatterns dark/green design, Tailwind+TS), live-wired to data. Run: `python -m web.backend.seed_dev` then `python -m uvicorn web.backend.app:app --port 8000`. Full details in memory `project_garagetec_plan.md`. Specs in `docs/superpowers/specs/`, plans in `docs/superpowers/plans/`.

## Phase 4 status
- **Segmentation: DONE.** Trajectory-based detector (hand-position; boundary = sustained return to address rest), over-split fixed (golf swing.MOV: 4→1), `MIN_SWING_FRAMES=26` rejects sub-second blips. Validated on real clips (smooth direct-export clip = flawless pose).
- **Norms: DONE (partial + honest).** `coach/norms/` is a package with `build_norms.py` + vendored `data/CaddieSet.csv` (MIT). Real cited bands ONLY for `shoulder_tilt_deg` (address/impact) + `spine_angle_deg` (address/impact), confidence "medium", sourced "mixed-skill **population**, NOT a validated ideal". Other 7 metrics confidence "none" (history-only). NOTE: these are MIXED-SKILL population (incl. poor golfers) → they are CONTEXT, not the ideal target.
- **Benchmarking: ACTIVE WORK.** Needs a tour-pro reference (below).

## The reframe (why we're hunting pro data)
- DROP "vs your best" — an amateur's best is still poor vs tour pros (bad-vs-less-bad). User confirmed.
- Benchmark against a TOUR-PRO / low-handicap reference, computed in OUR exact metric definitions.
- The CaddieSet "population" bands are not the ideal; the pro reference is.

## Findings — the 3 data threads

### A. GolfDB pro video → compute our own pro reference — **VIABLE, PRIMARY PATH** ✅
`github.com/wmcnally/golfdb` (CC BY-NC = fine for personal/non-commercial use).
- Annotation table `data/golfDB.pkl` (run `data/generate_splits.py`; needs scipy): 1400 rows, 246 players — **overwhelmingly real tour pros** (Tiger, Rory, Lydia Ko, Inbee Park, DJ…). ~6 celebrity non-pros, filterable by name.
- **449 face-on pro swings** across 117 pros (239 full-speed `slow==0`, 210 slow-mo). View col: 585 DTL / 461 face-on / 354 other.
- **Per-phase event labels ship** (the `events` array = 8 events ≈ our 8 phases) → bucket metrics by phase WITHOUT our detector. `events[0]`/`events[-1]` = clip trim.
- **Video:** download source via yt-dlp from `youtube_id`, crop by fractional `bbox` ([x,y,w,h]) at NATIVE resolution (see `data/preprocess_videos.py`; SKIP its final resize-to-160 — the shipped 160×160 `videos_160` is too small). Obtainable ~1456×1062 from 1080p source — plenty for pose. No download script exists → write a ~15-line yt-dlp loop over the ~209 unique face-on youtube_ids. Expect ~10–30% YouTube link rot.
- **Pose feasible** at that res. Caveats: "face-on" is loosely labeled (spot-check; drop `view=='other'`); prefer `slow==0` for clean frames.
- **Angle metrics = clean win** (shoulder tilt, spine angle, X-factor, turns). **Inch metrics = blocker** (no height/scale per clip) → FIX: redefine sway/positional metrics as **% of shoulder width** (scale-free) so pro swings + our swings are comparable without knowing heights. (This is a metric-definition decision to make.)
- **Effort: ~half-day to a day** (yt-dlp loop + crop tweak + run our existing `vision` pipeline). License OK for personal use.

### B. Deep literature research → published pro/scratch ranges — **NOT YET DONE; DO IT IN THE NEW SESSION**
Cross-check for A + covers metrics 2D video can't give (true 3D X-factor/rotations). Use the **deep-research workflow** with this question:
> Reputable, citable biomechanics reference values/ranges for SKILLED/low-handicap/tour-pro golfers for: shoulder lateral tilt (impact), hip tilt, shoulder/thorax turn, hip/pelvis turn, X-factor (thorax-pelvis separation at top), spine/forward-bend posture, early extension, hip sway, head sway, hand depth — at address/top/impact. For each: value/range, population (skill+n), method (2D vs 3D mocap, view), citation. Prioritize peer-reviewed golf biomechanics + TPI/AMM3D/GEARS/K-Vest. Flag where data is thin. (Prior session: the user STOPPED the deep-research workflow mid-launch — re-run it here.)

### C. CaddieSet good-golfer subset — **REJECTED (dead end)** ❌
Analyzed the vendored CSV. Ranked the 8 golfers by driver outcome → top tier = golfers 3, 2, 1. But a good-subset reference is NOT defensible: (a) only 3 golfers and they DISAGREE (shoulder_tilt impact medians 17.3/22.0/15.6 — 6° spread); (b) the apparent shift vs the mixed pool is largely a DRIVER-vs-IRON club-mix artifact (reverses under W1-only); (c) it unlocks NO new metrics (hip_turn/positional still clamp-junked). → KEEP the existing mixed-skill `shoulder_tilt_deg`/`spine_angle_deg` bands as "population context". Don't build a CaddieSet good-subset reference.

## Approach for the benchmarking build (once pro reference exists)
1. **Reference = tour-pro**, computed from GolfDB pro swings via OUR pose+metrics (per-phase distributions). Literature (B) = cross-check + 3D-only metrics.
2. **Two comparison layers:** (a) per-metric "vs tour-pro" deltas per phase; (b) **DTW swing-shape similarity** over phase-aligned per-frame joint-angle trajectories (build a pro reference TRAJECTORY from a GolfDB pro swing too) → overall similarity score + per-phase divergence.
3. **Inch metrics → normalize to % shoulder width** (scale-free) so amateur vs pro is comparable.
4. **Wire into:** coach `norms.json` (add a "pro/ideal" band tier alongside the "population" tier, with source+confidence) + a "vs tour pro" panel on the Review screen.
5. Recontextualize CaddieSet bands as "population (typical)", pro bands as "ideal".

## Concrete next steps (new session)
1. Read this doc + memory.
2. Run the deep-research workflow (B, question above) — adversarially-verified cited report.
3. Build the GolfDB pro-reference pipeline (A): a script to filter face-on pros → yt-dlp download → native-res crop → run `vision` pose+metrics, bucket by the shipped 8 events → per-phase pro reference (angle metrics; sway as % shoulder width). Vendor the resulting reference (numbers, not the videos) with attribution.
4. Decide final reference data (GolfDB primary; literature cross-check; CaddieSet population as context).
5. Build benchmarking (DTW + per-metric vs-pro deltas) + the Review UI panel. Follow the established loop: spec/plan → worktree → delegated subagent build → verify (run + screenshot) → merge.

## Key technical context / gotchas
- **Env:** Python 3.12 at `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe` (`py` launcher NOT on PATH — use full path). Installed: mediapipe **0.10.14** (pinned — newer dropped the Solutions API), opencv, numpy 1.26, **pandas (just installed globally by an analysis agent)**, pytest, pyinstaller, fastapi/uvicorn/httpx; Node at `C:\Program Files\nodejs`.
- **Reference clips in repo root (all gitignored `*.MOV`/`*.mov`/`*.mp4`):** `golf swing.MOV` (1 swing, phone-of-TV), `multiple_golf_swings.MOV` (multi-swing, phone-of-TV, 40s), `smooth_swing.mov` (GolfTEC sim, DIRECT export but rotated 90° portrait — rotate CW to landscape; clean pose). PRODUCTION GarageTEC video will be STANDARD orientation + proper lighting → no rotation handling needed in the pipeline (don't build it).
- **Build pattern:** every change = spec/plan in `docs/superpowers/` → git worktree+branch → delegated general-purpose subagent builds TDD → orchestrator verifies (runs tests + screenshots UI) → `--no-ff` merge → push → clean worktree. Worktree node_modules can lock removal → kill node first.
- **Multi-swing tuning still open (optional):** the merged-window case needs a CLEAN multi-swing clip to tune; `--single-swing` is the stopgap. Smooth single-swing was perfect.
- **GolfDB events → our phases:** Address, Toe-up(≈takeaway), Mid-backswing(≈lead-arm-parallel), Top, Mid-downswing(≈transition/shaft-parallel-down), Impact, Mid-follow-through, Finish. ~6/8 clean 1:1; derive transition + pre-impact shaft-parallel ourselves.
