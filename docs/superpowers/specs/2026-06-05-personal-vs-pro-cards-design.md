# Personal-vs-Tour-Pro Metric Cards — Design

**Date:** 2026-06-05
**Status:** Approved design (pre-implementation)
**Topic:** Merge the separate "vs ideal" bars and "vs Tour Pro" panels into a single
combined card per metric — color-coded by closeness to the tour pro, with a personal
trend arrow — and drive the body cards from the swing-replay playhead.

---

## 1. Goal

Today the app shows a metric's value, a hardcoded "vs ideal" range bar, and a
separate "vs Tour Pro" benchmark panel — in three different places. This redesign
**combines them into one card per metric** that answers, at a glance: *what did I do,
how does it compare to a tour pro, and am I trending the right way?*

Primary emphasis is on **body mechanics**, with **ball metrics** as a secondary row.
Body cards are **phase-aware** and update as the swing replay scrubs through
address → top → impact.

## 2. Scope

**In scope**
- A single combined metric card (Layout A) used for both body and ball metrics.
- Direction-aware stoplight coloring (green/yellow/red) vs the tour reference.
- A personal trend arrow (vs rolling average of recent swings).
- Turning `SwingReplay` into a **real video player** and a shared **phase
  timeline/jumper** that seeks the video; body cards follow the playhead (Live).
- Expanding the benchmark payload to cover **every** computed body metric × phase
  and **every** R50 ball metric, tagging each as benchmarked / needs-3D / raw.
- Adding newly-sourced references (X-Factor, X-Factor Stretch, Head Sway, Early
  Extension) and surfacing HLA.
- Per-screen layout: **Live** = cards + phase jumper; **Review** = the 3-phase table
  (now with tour comparison baked into cells) + ball cards.

**Out of scope**
- Changing any metric *calculation* (2D or 3D) or the 3D calibration flow.
- Building the live-capture/auto-record pipeline (separate, already specced).
- Sourcing references for metrics still without one (they render as raw cards).

## 3. Metric inventory (canonical)

This is the authoritative list of what becomes a card. **Direction modes:** `match`
(distance either way is bad), `higher` (above tour = green), `lower` (below tour =
green), `range` (a tolerant band, not a point). **2D/3D:** ◆ = comparable on the
current 2D pipeline; △ = value shown but comparison gated until the bay is calibrated
(3D). Tour numbers are GolfTEC tour averages unless noted.

### Body — benchmarked cards

| Card | Metric (`name`) | Dir | Phases (tour value) | 2D/3D |
|---|---|---|---|---|
| Shoulder Tilt | `shoulder_tilt_deg` | match | addr 10° ◆, top 36° △, impact 39° △ | tilt |
| Hip Tilt | `hip_tilt_deg` | match | addr 0° ◆, top 11° △, impact 14° △ | tilt |
| Spine Angle | `spine_angle_deg` | match | addr 36° ◆, top 2° △, impact 17° △ | tilt |
| Shoulder Turn | `shoulder_turn_deg` | match | top 89° △, impact 48° △ | 3D-only |
| Hip Turn | `hip_turn_deg` | match | top 48° △, impact 36° △ | 3D-only |
| Hip Sway | `hip_sway_in` | lower | top 3.9″ ◆, impact 1.6″ ◆ | 2D now |
| X-Factor | `x_factor_deg` | match | top **43°** △ | 3D-only |
| X-Factor Stretch | `x_factor_stretch_deg` | match | downswing **5°** △ | 3D-only |
| Head Sway | `head_sway_in` | range | top **3–6″** (≈4.5″) ◆ | 2D now |
| Early Extension | `early_extension_in` | lower | impact **0″** ◆ | 2D now |

New references (not from GolfTEC; from user research, stored separately with a source
tag): **X-Factor 43°** (midpoint of derived 41° = shoulder−hip turn and a ~45° source),
**X-Factor Stretch 5°**, **Head Sway 3–6″ band**, **Early Extension target 0″**.

### Body — raw cards (no reference yet)

| Card | Metric | Phases |
|---|---|---|
| Hand Depth | `hand_depth_in` | top, impact |

### Ball & Club — benchmarked cards (per club; impact only)

| Card | Key | Dir | Driver / 7-iron |
|---|---|---|---|
| Ball Speed | `ball_speed` | higher | 167 / 120 mph |
| Club Speed | `club_speed` | higher | 113 / 90 mph |
| Smash | `smash` | higher | 1.48 / 1.33 |
| Carry | `carry` | higher | 275 / 172 yds |
| Launch | `launch` (vla) | match | 10.9 / 16.3° |
| Spin | `spin` (total_spin) | match | 2686 / 7097 rpm |
| Attack Angle | `attack_angle` | match | −1.3 / −4.3° |

### Ball & Club — raw cards (no reference)

`club_path` (°), `face_to_target` (°), `spin_axis` (°), `back_spin` (rpm),
`side_spin` (rpm), and **`hla`** (horizontal launch °) — HLA is currently received
but not surfaced anywhere; this adds it as a raw card.

## 4. Stoplight color model

Two boundaries per metric create three zones: **green** ≤ first, **yellow** between,
**red** > second. Distance is measured from the tour number and applied per direction
mode (for `higher`/`lower`, the "good" side is entirely green; bands only measure the
bad side). `range` uses the band edges as the green zone.

| Metric | Dir | Green ≤ | Yellow ≤ | Notes |
|---|---|---|---|---|
| Shoulder/Hip Tilt, Spine | match | 3° | 6° | |
| Shoulder Turn | match | 5° | 12° | |
| Hip Turn | match | 5° | 10° | |
| X-Factor | match | 5° | 10° | target 43° |
| X-Factor Stretch | match | 2° | 4° | target 5° |
| Hip Sway | lower | +0.5″ | +1.5″ | below tour = green |
| Head Sway | range | in 3–6″ | ±1.5″ outside | else red |
| Early Extension | lower | 1″ | 2″ | target 0″ |
| Ball / Club Speed | higher | 2.5 below | 5 below | above = green; mph |
| Smash | higher | .03 below | .05 below | above = green |
| Carry | higher | 5 below | 10 below | above = green; yds |
| Launch | match | 1° | 2° | |
| Spin | match | 250 | 500 | rpm |
| Attack Angle | match | 0.75° | 1.5° | |

All values are **first-pass and tunable**, defined in **one config map**
(`coach/metric_thresholds.py`) so they can be adjusted in a single place. The zone is
**computed server-side** and returned with each card so the frontend just renders the
color (no threshold logic duplicated in TS).

## 5. Trend arrow

- **Basis:** the rolling average of the user's **recent swings** (default last ~10).
  **Ball** trends are scoped to the **same club**; **body** trends are across recent
  swings (mechanics are fairly club-independent) and per **(metric, phase)**.
- **Arrow direction** (▲/▼): this swing's value vs that rolling average.
- **Arrow color:** **green if the move went *toward* the tour target, red if *away*** —
  i.e. color reflects whether the change helped, independent of up/down. Neutral
  (no change / insufficient history) = grey dash.
- Computed on the **frontend** from the existing history endpoints
  (`/api/history` for body, `/api/ball-history` for ball), sliced to the recent window.

## 6. Card component (Layout A)

One card component serves body and ball. Fields:

- **Header row:** metric name · *(body only)* inline phase badge (Address/Top/Impact) ·
  trend pill (▲/▼ value, colored toward/away) on the right.
- **Value:** large mono number + unit.
- **Comparison line:** `Tour <target> · <±delta>`, the delta colored by zone.
- **Stoplight:** colored **left accent bar** (green/yellow/red).

**Card states:**
1. **Benchmarked** — full color, delta, trend. (zone present)
2. **Needs-3D** — value shown; accent + comparison greyed with a `NEEDS 3D · tour <n>`
   chip; no color until calibration lands, then it lights up automatically.
3. **Raw** — value + trend shown; greyed `no tour avg`, no color (metrics with no
   reference).
4. **Off-phase** — when a metric isn't measured at the current phase (e.g. Shoulder
   Turn at Address, Early Extension anywhere but Impact), the card **dims in place**
   and shows `— measured at <phase>`. The grid does **not** reflow as you scrub.

## 7. Replay sync & phase model (Live)

- **`SwingReplay` becomes a real `<video>`** playing the swing's annotated clip
  (`media` → `mediaUrl`), with play/pause, realtime/slow-mo (playbackRate), and a
  scrubber. It exposes the current playback time to its parent.
- **Phase model:** the swing's `Moments` (`kind` + `time_s`) define phase timestamps
  (today: address/top/impact). The **current phase** = the latest moment whose
  `time_s ≤ currentTime`. Body cards render each metric at the current phase.
- **Phase timeline/jumper:** extract Review's inline 8-phase timeline into a shared
  `PhaseTimeline` component. On **Live** it is added to the replay area; tapping a
  phase **seeks the video** to that moment's timestamp (phases without a stored moment
  are shown inactive). On **Review** it keeps its current role and also highlights the
  active phase.
- **Fallback:** if a swing has no annotated video/moments, the replay shows the
  current placeholder and cards default to the Impact phase (no auto-follow).

## 8. Per-screen layout

**Live** (`LiveScreen`)
- Top: real `SwingReplay` (with phase jumper) + AI Coach Read.
- **Body Mechanics · vs Tour Pro** — primary grid of larger cards, phase-following.
- **Ball & Club · vs Tour Pro** — secondary grid of smaller cards (benchmarked first,
  then raw, de-emphasized). Appears once a shot is matched; club from active club.

**Review** (`ReviewScreen`)
- Keeps the **3-phase body table** (Metric × Address/Top/Impact). Each cell shows the
  user's value **colored by the stoplight** vs that phase's tour target, with
  `±delta · tour <n>` muted beneath. Needs-3D cells show the value greyed with
  `needs 3D`; phases with no reference show `—`; raw metrics show `no tour avg`.
- **Ball & Club cards** (same Layout-A cards) below the table (single phase).
- Keeps the 8-phase `PhaseTimeline`; it highlights the active phase / seeks the video.

## 9. Data & backend changes

- **`coach/metric_thresholds.py` (new):** single config map of `{metric: {direction,
  green, yellow}}` plus `zone_for(metric, value, target) -> 'green'|'yellow'|'red'`.
- **`coach/supplementary_reference.json` (new):** X-Factor (top 43°), X-Factor Stretch
  (downswing 5°), Head Sway (top, band 3–6″), Early Extension (impact, target 0″),
  each tagged with a `source`. Kept separate from the authoritative
  `golftec_reference.json`.
- **`coach/golftec.py`:** expand the benchmark output to emit a row for **every
  computed body metric × phase** (not only those with a GolfTEC target). Merge in the
  supplementary references. Each row gains `direction`, `zone` (or null), and `state`
  (`ok` | `needs_3d` | `raw`).
- **`coach/ball_reference.py`:** `benchmark_ball` rows gain `direction` + `zone`;
  `raw_ball_fields` adds `hla`.
- **`web/backend/api_swings.py`:** assemble the expanded body rows + ball rows into the
  swing-detail payload (shape additive — existing keys preserved).
- The swing-detail payload already returns `media` and `moments` for the replay sync.

## 10. Frontend components

- **`components/MetricCard.tsx`** — rebuilt as the combined Layout-A card; one
  component for body (with phase badge) and ball (without). Props include
  `value, unit, target, delta, zone, state, phase?, trend {delta, towardPro}`.
- **`components/PhaseTimeline.tsx` (new)** — extracted shared phase scrubber;
  `{ moments, activePhase, onSeek }`. Used by Live (seeks video) and Review.
- **`components/SwingReplay.tsx`** — real `<video>`, exposes `currentTime`/phase via
  callback; controlled seek from `PhaseTimeline`.
- **`lib/metricConfig.ts` (new)** — display metadata only (labels, units, card order,
  which group, which phases apply). Thresholds/zone live server-side.
- **`lib/trend.ts` (new)** — rolling-average trend + toward/away-from-pro color.
- **`pages/LiveScreen.tsx`** — body + ball card grids; phase from replay playhead.
- **`pages/ReviewScreen.tsx`** — table cells colored by zone + tour deltas; ball cards
  below; timeline highlights/seeks.
- **`lib/api.ts` / `lib/types.ts`** — extended benchmark/ball row fields, HLA in raw.

## 11. Testing

- **Backend:** `zone_for` per direction mode and boundary (green/yellow/red edges);
  supplementary references load + merge; benchmark emits rows for all metric×phase with
  correct `state` (ok/needs_3d/raw); ball rows carry direction+zone; HLA in raw; payload
  shape.
- **Frontend:** MetricCard renders each state (benchmarked/needs-3d/raw/off-phase) and
  trend color (toward vs away); phase derivation from playback time; PhaseTimeline seek;
  Review table cell coloring; per-club ball trend.

## 12. Risks / open items

- **Phase jumper granularity:** only address/top/impact have stored moments today, so
  the jumper has 3 active stops (the other 5 timeline phases are inactive). Acceptable;
  expands automatically if more moments are detected later.
- **X-Factor target (43°)** and the **Head Sway band (3–6″)** are opinionated /
  wide-range by design; flagged as tunable in the config.
- **Card density:** ~10 body + ~13 ball cards. Managed via grouping (benchmarked first,
  raw de-emphasized) and the body-over-ball size hierarchy.
- **No-video swings** fall back to a static replay + Impact-phase cards.
