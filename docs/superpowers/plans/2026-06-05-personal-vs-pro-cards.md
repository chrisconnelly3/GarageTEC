# Personal-vs-Tour-Pro Metric Cards — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the separate "vs ideal" bars and "vs Tour Pro" panels with one combined, direction-aware stoplight card per metric (body + ball), add a personal trend arrow, and drive the body cards from a real swing-replay video + phase jumper.

**Architecture:** Zone (green/yellow/red) is computed **server-side** from one tunable threshold config and returned on each benchmark row; the trend arrow is computed **client-side** from existing history endpoints. `SwingReplay` becomes a real `<video>`; a shared `PhaseTimeline` seeks it; body cards render the metric at the playhead's current phase. Live = cards + jumper; Review = the 3-phase table (cells colored vs tour) + ball cards.

**Tech Stack:** Python 3.12 (`C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`), pytest, FastAPI; React + TypeScript + Vite + Vitest + Tailwind; recharts already present.

**Spec:** `docs/superpowers/specs/2026-06-05-personal-vs-pro-cards-design.md`

**Conventions (from prior sessions):**
- Run python tests: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q`
- Frontend tests: from `web/frontend`, `npm test` (vitest run). Build: `npm run build`. Node at `C:\Program Files\nodejs`.
- Frontend tests live as `src/**/*.test.tsx`, NOT `__tests__/`.
- Frontend changes need `npm run build` + a uvicorn restart to show in the served app.
- CRLF warnings on commit are benign.
- Commit to `main` directly (per user).

---

## File Structure

**Backend (new/modified)**
- `coach/metric_thresholds.py` *(new)* — single threshold config + `zone_for()`. The only place stoplight bands live.
- `coach/norms/pro_reference/supplementary_reference.json` *(new)* — X-Factor, X-Factor Stretch, Head Sway, Early Extension references (non-GolfTEC, source-tagged).
- `coach/golftec.py` *(modify)* — merge supplementary refs into `load()`; `benchmark_metrics()` now emits a row for **every** computed body metric×phase (raw included) with `direction`, `zone`, `state`.
- `coach/ball_reference.py` *(modify)* — `benchmark_ball()` rows gain `direction` + `zone`; `raw_ball_fields()` gains `hla`.
- `web/backend/api_swings.py` *(unchanged logic; covered by tests)* — already returns `benchmarks` / `ball_benchmarks` / `ball_raw`; rows are now richer.

**Frontend (new/modified)**
- `web/frontend/src/lib/types.ts` *(modify)* — richer `Benchmark` / `BallBenchmark`; `MetricZone` / `MetricState` types.
- `web/frontend/src/lib/metricConfig.ts` *(new)* — card display metadata: which metrics are cards, label, unit, group, phase order.
- `web/frontend/src/lib/trend.ts` *(new)* — rolling-average trend + toward/away-from-pro color.
- `web/frontend/src/lib/phase.ts` *(new)* — pure `phaseAtTime(moments, t)` + ordered phase helpers.
- `web/frontend/src/components/MetricCard.tsx` *(rewrite)* — combined Layout-A card, all four states.
- `web/frontend/src/components/PhaseTimeline.tsx` *(new)* — shared phase scrubber (extracted from Review).
- `web/frontend/src/components/SwingReplay.tsx` *(rewrite)* — real `<video>`, emits current time/phase, controlled seek.
- `web/frontend/src/pages/LiveScreen.tsx` *(modify)* — body + ball card grids; phase from replay; jumper in replay area.
- `web/frontend/src/pages/ReviewScreen.tsx` *(modify)* — table cells colored vs tour; ball cards below.
- `web/frontend/src/lib/api.ts` *(modify)* — no new endpoints; only type wiring.

---

## TASK GROUP A — BACKEND

### Task 1: Threshold config + `zone_for()`

**Files:**
- Create: `coach/metric_thresholds.py`
- Test: `coach/tests/test_metric_thresholds.py`

- [ ] **Step 1: Write the failing test**

```python
# coach/tests/test_metric_thresholds.py
from coach import metric_thresholds as mt


def test_match_zones():
    # spine: match, green<=3, yellow<=6
    assert mt.zone_for("spine_angle_deg", 18.0, 17.0) == "green"   # |+1| <= 3
    assert mt.zone_for("spine_angle_deg", 22.0, 17.0) == "yellow"  # |+5| in (3,6]
    assert mt.zone_for("spine_angle_deg", 25.0, 17.0) == "red"     # |+8| > 6


def test_higher_is_better_above_target_is_green():
    # ball_speed: higher, green<=2.5 below, yellow<=5 below
    assert mt.zone_for("ball_speed", 171.0, 167.0) == "green"   # above tour
    assert mt.zone_for("ball_speed", 165.0, 167.0) == "green"   # 2 below
    assert mt.zone_for("ball_speed", 163.0, 167.0) == "yellow"  # 4 below
    assert mt.zone_for("ball_speed", 160.0, 167.0) == "red"     # 7 below


def test_lower_is_better_below_target_is_green():
    # hip_sway: lower, green<=+0.5 above, yellow<=+1.5 above
    assert mt.zone_for("hip_sway_in", 1.0, 1.6) == "green"    # below tour
    assert mt.zone_for("hip_sway_in", 2.0, 1.6) == "green"    # +0.4
    assert mt.zone_for("hip_sway_in", 2.8, 1.6) == "yellow"   # +1.2
    assert mt.zone_for("hip_sway_in", 3.5, 1.6) == "red"      # +1.9


def test_range_uses_absolute_distance_from_midpoint():
    # head_sway: range, green<=1.5 from 4.5 (=> 3..6), yellow<=3
    assert mt.zone_for("head_sway_in", 4.0, 4.5) == "green"
    assert mt.zone_for("head_sway_in", 7.0, 4.5) == "yellow"  # 2.5 out
    assert mt.zone_for("head_sway_in", 8.5, 4.5) == "red"     # 4 out


def test_unknown_metric_or_missing_target_is_none():
    assert mt.zone_for("hand_depth_in", 13.0, None) is None
    assert mt.zone_for("not_a_metric", 1.0, 2.0) is None


def test_direction_lookup():
    assert mt.direction_for("ball_speed") == "higher"
    assert mt.direction_for("hip_sway_in") == "lower"
    assert mt.direction_for("spine_angle_deg") == "match"
    assert mt.direction_for("hand_depth_in") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_metric_thresholds.py -q`
Expected: FAIL (module `coach.metric_thresholds` not found).

- [ ] **Step 3: Write minimal implementation**

```python
# coach/metric_thresholds.py
"""Single source of truth for stoplight thresholds. Two boundaries per metric
create three zones: green <= first, yellow <= second, red > second. Distance is
measured from the tour target, applied per direction mode:
  match  -> |value - target| (either side is bad)
  range  -> |value - target| (target is a band midpoint; same math as match)
  higher -> max(0, target - value)  (above target is always green)
  lower  -> max(0, value - target)  (below target is always green)
All numbers are first-pass and intentionally easy to tune here.
"""

# metric_key -> (direction, green_boundary, yellow_boundary)
THRESHOLDS = {
    # --- body ---
    "shoulder_tilt_deg":     ("match",  3,    6),
    "hip_tilt_deg":          ("match",  3,    6),
    "spine_angle_deg":       ("match",  3,    6),
    "shoulder_turn_deg":     ("match",  5,    12),
    "hip_turn_deg":          ("match",  5,    10),
    "x_factor_deg":          ("match",  5,    10),
    "x_factor_stretch_deg":  ("match",  2,    4),
    "hip_sway_in":           ("lower",  0.5,  1.5),
    "head_sway_in":          ("range",  1.5,  3),
    "early_extension_in":    ("lower",  1,    2),
    # --- ball (keys match ball_reference benchmark keys) ---
    "ball_speed":            ("higher", 2.5,  5),
    "club_speed":            ("higher", 2.5,  5),
    "smash":                 ("higher", 0.03, 0.05),
    "carry":                 ("higher", 5,    10),
    "launch":                ("match",  1,    2),
    "spin":                  ("match",  250,  500),
    "attack_angle":          ("match",  0.75, 1.5),
}


def direction_for(metric):
    cfg = THRESHOLDS.get(metric)
    return cfg[0] if cfg else None


def zone_for(metric, value, target):
    """Return 'green' | 'yellow' | 'red', or None when the metric is unknown or
    no target is available."""
    cfg = THRESHOLDS.get(metric)
    if cfg is None or value is None or target is None:
        return None
    direction, green, yellow = cfg
    d = value - target
    if direction == "higher":
        m = max(0.0, -d)
    elif direction == "lower":
        m = max(0.0, d)
    else:  # match, range
        m = abs(d)
    if m <= green:
        return "green"
    if m <= yellow:
        return "yellow"
    return "red"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_metric_thresholds.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add coach/metric_thresholds.py coach/tests/test_metric_thresholds.py
git commit -m "feat(coach): metric_thresholds config + zone_for stoplight engine"
```

---

### Task 2: Supplementary references + merged loader

**Files:**
- Create: `coach/norms/pro_reference/supplementary_reference.json`
- Modify: `coach/golftec.py` (the `load()` function)
- Test: `coach/tests/test_golftec.py` (add cases)

- [ ] **Step 1: Write the failing test (append to `coach/tests/test_golftec.py`)**

```python
def test_supplementary_references_merged():
    ref = golftec.load()
    # X-Factor @ top = 43, 3D-gated (not 2D-comparable)
    xf = ref["x_factor_deg"]["contexts"]["top"]
    assert xf["value"] == 43 and xf["two_d_comparable_now"] is False
    # Early Extension @ impact = 0, comparable on 2D now
    ee = ref["early_extension_in"]["contexts"]["impact"]
    assert ee["value"] == 0 and ee["two_d_comparable_now"] is True
    # Head Sway @ top midpoint 4.5, 2D-comparable
    hs = ref["head_sway_in"]["contexts"]["top"]
    assert hs["value"] == 4.5 and hs["two_d_comparable_now"] is True
    # X-Factor Stretch @ downswing = 5
    assert ref["x_factor_stretch_deg"]["contexts"]["downswing"]["value"] == 5
    # GolfTEC originals still present
    assert ref["shoulder_tilt_deg"]["contexts"]["address"]["value"] == 10


def test_compare_uses_supplementary_target():
    # early extension: 2D-comparable now, so a delta is returned without 3D
    c = golftec.compare("early_extension_in", "impact", 1.5)
    assert c["comparable"] is True and c["target"] == 0 and c["delta"] == 1.5
```

- [ ] **Step 2: Run to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_golftec.py -q`
Expected: FAIL (`KeyError: 'x_factor_deg'`).

- [ ] **Step 3a: Create the supplementary reference file**

```json
{
  "x_factor_deg": {
    "metric": "x_factor_deg",
    "contexts": {
      "top": {"value": 43, "two_d_comparable_now": false,
              "source": "derived shoulder_turn-hip_turn (41) + research (~45), midpoint 43"}
    }
  },
  "x_factor_stretch_deg": {
    "metric": "x_factor_stretch_deg",
    "contexts": {
      "downswing": {"value": 5, "two_d_comparable_now": false,
                    "source": "biomechanics literature (~5 deg)"}
    }
  },
  "head_sway_in": {
    "metric": "head_sway_in",
    "contexts": {
      "top": {"value": 4.5, "two_d_comparable_now": true,
              "source": "research: tour trail-side head sway ~3-6 in during backswing; 4.5 midpoint"}
    }
  },
  "early_extension_in": {
    "metric": "early_extension_in",
    "contexts": {
      "impact": {"value": 0, "two_d_comparable_now": true,
                 "source": "GolfTEC pass/fail screen: pros ~0 early extension"}
    }
  }
}
```

- [ ] **Step 3b: Merge it in `coach/golftec.py`**

Replace the `_PATH` block and `load()` with:

```python
_DIR = os.path.join(os.path.dirname(__file__), "norms", "pro_reference")
_PATH = os.path.join(_DIR, "golftec_reference.json")
_SUPP_PATH = os.path.join(_DIR, "supplementary_reference.json")


def load(path=None, supp_path=None):
    """Authoritative GolfTEC references merged with the supplementary (non-GolfTEC,
    source-tagged) references. GolfTEC wins on any key collision."""
    with open(path or _PATH, "r", encoding="utf-8") as f:
        ref = json.load(f)
    sp = supp_path or _SUPP_PATH
    if os.path.exists(sp):
        with open(sp, "r", encoding="utf-8") as f:
            for name, entry in json.load(f).items():
                ref.setdefault(name, entry)   # do not override GolfTEC
    return ref
```

- [ ] **Step 4: Run to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_golftec.py -q`
Expected: PASS (existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add coach/norms/pro_reference/supplementary_reference.json coach/golftec.py coach/tests/test_golftec.py
git commit -m "feat(coach): supplementary tour references (x-factor, stretch, head sway, early ext) merged into loader"
```

---

### Task 3: Expand `benchmark_metrics` — all metric×phase rows + direction/zone/state

**Files:**
- Modify: `coach/golftec.py` (`benchmark_metrics`)
- Test: `coach/tests/test_golftec.py` (add cases)

- [ ] **Step 1: Write the failing tests (append)**

```python
def test_benchmark_row_has_zone_and_state_for_comparable():
    metrics = [{"name": "shoulder_tilt_deg", "context": "address",
                "value": 12.0, "unit": "deg", "method": "exact"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "ok"
    assert row["direction"] == "match"
    assert row["zone"] == "green"        # |12-10|=2 <= 3
    assert row["target"] == 10 and row["delta"] == 2.0


def test_benchmark_needs_3d_has_no_zone():
    metrics = [{"name": "shoulder_turn_deg", "context": "top",
                "value": 50.0, "unit": "deg", "method": "foreshortening_2d"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "needs_3d" and row["zone"] is None
    assert row["comparable"] is False and row["target"] == 89


def test_benchmark_emits_raw_row_for_unreferenced_metric():
    metrics = [{"name": "hand_depth_in", "context": "impact",
                "value": 9.2, "unit": "in", "method": "shoulder_ratio_0.24"}]
    row = golftec.benchmark_metrics(metrics)[0]
    assert row["state"] == "raw"
    assert row["target"] is None and row["zone"] is None and row["delta"] is None
    assert row["value"] == 9.2
```

- [ ] **Step 2: Run to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_golftec.py -q`
Expected: FAIL (`KeyError: 'state'`, and the raw metric is currently skipped).

- [ ] **Step 3: Rewrite `benchmark_metrics` in `coach/golftec.py`**

Add the import at the top of the file (below the existing imports):

```python
from coach import metric_thresholds
```

Replace the whole `benchmark_metrics` function with:

```python
def benchmark_metrics(metrics, ref=None):
    """Build 'vs tour pro' rows for a swing's metrics. `metrics` is a list of
    dicts {name, context, value, unit, method}. Emits a row for EVERY
    (name, context) present (raw metrics included), so the UI can render a card
    for everything. 3D availability comes from the row's own method
    (`triangulated_3d*`); when both a 2D and a 3D row exist for the same
    (name, context), the comparable one wins.

    Each row: {name, context, value, unit, target, delta, comparable, reason,
    direction, zone, state}. state is one of:
      'ok'       - comparable, has a zone color
      'needs_3d' - has a target but gated until 3D is available (zone None)
      'raw'      - no tour target at all (target/zone/delta None)
    """
    ref = load() if ref is None else ref
    rows = {}
    for m in metrics:
        name, context, value = m.get("name"), m.get("context"), m.get("value")
        if name is None or context is None or value is None:
            continue
        has_3d = str(m.get("method") or "").startswith("triangulated_3d")
        c = compare(name, context, value, has_3d=has_3d, ref=ref)
        no_target = c["reason"] in ("no_golftec_target", "no_phase_target")
        if no_target:
            state, zone = "raw", None
        elif c["comparable"]:
            state = "ok"
            zone = metric_thresholds.zone_for(name, value, c["target"])
        else:
            state, zone = "needs_3d", None
        row = {
            "name": name, "context": context, "value": round(value, 1),
            "unit": m.get("unit"),
            "target": None if no_target else c["target"],
            "delta": round(c["delta"], 1) if c["delta"] is not None else None,
            "comparable": c["comparable"],
            "reason": None if no_target else c["reason"],
            "direction": metric_thresholds.direction_for(name),
            "zone": zone,
            "state": state,
        }
        key = (name, context)
        prev = rows.get(key)
        # comparable rows win; otherwise first-seen wins
        if prev is None or (row["comparable"] and not prev["comparable"]):
            rows[key] = row
    return sorted(rows.values(),
                  key=lambda r: (r["name"], _PHASE_ORDER.get(r["context"], 9)))
```

- [ ] **Step 4: Run to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_golftec.py -q`
Expected: PASS. (If a prior test asserted unreferenced metrics are *omitted*, update it — emitting raw rows is the new intended behavior.)

- [ ] **Step 5: Commit**

```bash
git add coach/golftec.py coach/tests/test_golftec.py
git commit -m "feat(coach): benchmark rows gain direction/zone/state and emit raw rows for all metrics"
```

---

### Task 4: Ball benchmark direction/zone + surface HLA

**Files:**
- Modify: `coach/ball_reference.py` (`benchmark_ball`, `raw_ball_fields`)
- Test: `coach/tests/test_ball_reference.py` (add cases)

- [ ] **Step 1: Write the failing tests (append)**

```python
from coach import ball_reference as br


def test_ball_benchmark_has_direction_and_zone():
    shot = {"ball_speed": 171.0, "club_speed": 115.0, "vla": 12.2,
            "total_spin": 3450, "attack_angle": 1.5, "carry": 281.0}
    rows = {r["key"]: r for r in br.benchmark_ball(shot, "Driver")}
    # higher-is-better, above tour -> green
    assert rows["ball_speed"]["direction"] == "higher"
    assert rows["ball_speed"]["zone"] == "green"
    # match, spin way over -> red
    assert rows["spin"]["direction"] == "match"
    assert rows["spin"]["zone"] == "red"


def test_raw_ball_fields_includes_hla():
    raw = {r["key"]: r for r in br.raw_ball_fields({"hla": 0.8})}
    assert raw["hla"]["value"] == 0.8 and raw["hla"]["unit"] == "deg"
```

- [ ] **Step 2: Run to verify it fails**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_ball_reference.py -q`
Expected: FAIL (`KeyError: 'direction'`; no `hla` key).

- [ ] **Step 3: Edit `coach/ball_reference.py`**

Add an import near the existing `import json` / `import math` block:

```python
from coach import metric_thresholds
```

In `benchmark_ball`, replace the `out.append({...})` block with:

```python
        out.append({"key": key, "label": label, "unit": unit,
                    "value": v, "target": target, "delta": delta,
                    "near": abs(delta) <= tol,
                    "direction": metric_thresholds.direction_for(key),
                    "zone": metric_thresholds.zone_for(key, v, target)})
```

In `raw_ball_fields`, add an HLA entry to the returned list (after `side_spin`):

```python
        {"key": "hla",            "label": "Horiz. launch",  "unit": "deg",
         "value": _deg(shot.get("hla"))},
```

- [ ] **Step 4: Run to verify it passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest coach/tests/test_ball_reference.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add coach/ball_reference.py coach/tests/test_ball_reference.py
git commit -m "feat(coach): ball benchmarks gain direction/zone; surface HLA as a raw field"
```

---

### Task 5: API payload sanity test

**Files:**
- Test: `web/backend/tests/test_api_swings.py` (add a case)

- [ ] **Step 1: Write the test (append, mirroring the file's existing fixture style)**

```python
def test_swing_detail_benchmarks_carry_zone_and_state(client_with_seeded_swing):
    # uses whatever fixture the file already uses to seed a ready swing + shot
    client, swing_id = client_with_seeded_swing
    body = client.get(f"/api/swings/{swing_id}").json()
    # every body benchmark row now carries state + direction
    assert all("state" in r and "direction" in r for r in body["benchmarks"])
    # ball rows carry zone/direction
    assert all("zone" in r and "direction" in r for r in body["ball_benchmarks"])
    # HLA present in raw
    assert any(r["key"] == "hla" for r in body["ball_raw"])
```

> If the existing test file uses a different fixture/name, reuse that one — open `web/backend/tests/test_api_swings.py`, copy its swing-detail fixture, and adapt the asserts above. Do not invent a new fixture.

- [ ] **Step 2: Run to verify it fails or passes**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest web/backend/tests/test_api_swings.py -q`
Expected: PASS (the API just forwards the now-richer rows; this guards the shape).

- [ ] **Step 3: Run the FULL backend suite**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q`
Expected: all pass (fix any prior test that assumed the old benchmark shape).

- [ ] **Step 4: Commit**

```bash
git add web/backend/tests/test_api_swings.py
git commit -m "test(api): guard benchmark zone/state/direction + HLA in swing detail"
```

---

## TASK GROUP B — FRONTEND DATA LAYER

### Task 6: Types

**Files:**
- Modify: `web/frontend/src/lib/types.ts`

- [ ] **Step 1: Add the new types / extend existing ones**

Add near the other metric types:

```typescript
export type MetricZone = "green" | "yellow" | "red";
export type MetricState = "ok" | "needs_3d" | "raw";
export type MetricDirection = "match" | "higher" | "lower" | "range";
```

Replace the existing `Benchmark` interface with:

```typescript
export interface Benchmark {
  name: string; context: string; value: number; unit: string | null;
  target: number | null; delta: number | null; comparable: boolean;
  reason: string | null;
  direction: MetricDirection | null;
  zone: MetricZone | null;
  state: MetricState;
}
```

Replace the existing `BallBenchmark` interface with:

```typescript
export interface BallBenchmark {
  key: string; label: string; unit: string; value: number; target: number;
  delta: number; near: boolean;
  direction: MetricDirection | null;
  zone: MetricZone | null;
}
```

- [ ] **Step 2: Typecheck**

Run (from `web/frontend`): `npx tsc -b --noEmit` (or `npm run build`)
Expected: type errors only where consumers must adapt (next tasks fix them). Confirm no errors in `types.ts` itself.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/lib/types.ts
git commit -m "feat(types): zone/state/direction on benchmark + ball benchmark rows"
```

---

### Task 7: Card display config

**Files:**
- Create: `web/frontend/src/lib/metricConfig.ts`
- Modify: `web/frontend/src/lib/format.ts` (extend `METRIC_LABEL`)
- Test: `web/frontend/src/lib/metricConfig.test.ts`

- [ ] **Step 1: Extend `METRIC_LABEL` in `format.ts`**

```typescript
export const METRIC_LABEL: Record<string, string> = {
  shoulder_tilt_deg: "Shoulder Tilt", hip_tilt_deg: "Hip Tilt",
  shoulder_turn_deg: "Shoulder Turn", hip_turn_deg: "Hip Turn",
  spine_angle_deg: "Spine Angle", hand_depth_in: "Hand Depth",
  early_extension_in: "Early Ext.", hip_sway_in: "Hip Sway",
  head_sway_in: "Head Sway",
  x_factor_deg: "X-Factor", x_factor_stretch_deg: "X-Factor Stretch",
};
```

- [ ] **Step 2: Write the failing test**

```typescript
// web/frontend/src/lib/metricConfig.test.ts
import { describe, it, expect } from "vitest";
import { BODY_CARD_ORDER, BALL_CARD_ORDER, PHASES } from "./metricConfig";

describe("metricConfig", () => {
  it("lists body cards in the agreed order, X-Factor present", () => {
    expect(BODY_CARD_ORDER[0]).toBe("shoulder_tilt_deg");
    expect(BODY_CARD_ORDER).toContain("x_factor_deg");
    expect(BODY_CARD_ORDER).toContain("hand_depth_in"); // raw, still a card
  });
  it("orders ball benchmarked keys before raw keys", () => {
    expect(BALL_CARD_ORDER.indexOf("ball_speed"))
      .toBeLessThan(BALL_CARD_ORDER.indexOf("club_path"));
  });
  it("exposes the three card phases", () => {
    expect(PHASES).toEqual(["address", "top", "impact"]);
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run (from `web/frontend`): `npm test -- metricConfig`
Expected: FAIL (module not found).

- [ ] **Step 4: Create `metricConfig.ts`**

```typescript
// web/frontend/src/lib/metricConfig.ts
// Display metadata for the metric cards. Thresholds/zones live server-side; this
// file only decides which metrics are cards, their order, and grouping.

// The three phases the body cards switch between (driven by the replay playhead).
export const PHASES = ["address", "top", "impact"] as const;
export type Phase = (typeof PHASES)[number];

// Body cards, in display order (benchmarked first, raw last). Names match the
// metric `name` field from the API.
export const BODY_CARD_ORDER = [
  "shoulder_tilt_deg",
  "hip_tilt_deg",
  "spine_angle_deg",
  "shoulder_turn_deg",
  "hip_turn_deg",
  "x_factor_deg",
  "x_factor_stretch_deg",
  "hip_sway_in",
  "head_sway_in",
  "early_extension_in",
  "hand_depth_in", // raw (no tour ref yet)
];

// Ball cards: benchmarked keys (from ball_benchmarks) first, then raw keys
// (from ball_raw). Keys match the API row `key`.
export const BALL_BENCHMARK_ORDER = [
  "ball_speed", "club_speed", "smash", "carry", "launch", "spin", "attack_angle",
];
export const BALL_RAW_ORDER = [
  "club_path", "face_to_target", "spin_axis", "back_spin", "side_spin", "hla",
];
export const BALL_CARD_ORDER = [...BALL_BENCHMARK_ORDER, ...BALL_RAW_ORDER];

// Units for x-factor cards (others come from the API row's unit).
export const METRIC_UNIT: Record<string, string> = {
  x_factor_deg: "deg", x_factor_stretch_deg: "deg",
};
```

- [ ] **Step 5: Run to verify it passes**

Run (from `web/frontend`): `npm test -- metricConfig`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/lib/metricConfig.ts web/frontend/src/lib/format.ts web/frontend/src/lib/metricConfig.test.ts
git commit -m "feat(frontend): metric card display config + labels for x-factor"
```

---

### Task 8: Trend util (rolling average + toward/away color)

**Files:**
- Create: `web/frontend/src/lib/trend.ts`
- Test: `web/frontend/src/lib/trend.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// web/frontend/src/lib/trend.test.ts
import { describe, it, expect } from "vitest";
import { computeTrend } from "./trend";

describe("computeTrend", () => {
  it("returns neutral when history is too short", () => {
    expect(computeTrend([], 10, 9, "match")).toEqual({ delta: 0, towardPro: null });
  });
  it("match: moving closer to target is toward (green)", () => {
    // recent avg = 14, now 11, target 10 -> closer -> toward
    const t = computeTrend([{ value: 13 }, { value: 15 }], 11, 10, "match");
    expect(t.delta).toBe(-3); // 11 - 14
    expect(t.towardPro).toBe(true);
  });
  it("higher: increasing is toward regardless of target side", () => {
    const t = computeTrend([{ value: 160 }, { value: 162 }], 168, 167, "higher");
    expect(t.delta).toBe(7); // 168 - 161
    expect(t.towardPro).toBe(true);
  });
  it("lower: decreasing is toward", () => {
    const t = computeTrend([{ value: 3.0 }, { value: 3.2 }], 2.4, 1.6, "lower");
    expect(t.towardPro).toBe(true);
  });
  it("no target (raw) -> toward unknown, still reports delta", () => {
    const t = computeTrend([{ value: 13 }, { value: 14 }], 15, null, "match");
    expect(t.delta).toBe(1.5);
    expect(t.towardPro).toBe(null);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/frontend`): `npm test -- trend`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `trend.ts`**

```typescript
// web/frontend/src/lib/trend.ts
import type { MetricDirection } from "./types";

const WINDOW = 10; // rolling-average window of recent prior swings

export interface Trend {
  delta: number;          // current - rolling avg (sign = arrow direction)
  towardPro: boolean | null; // did the move go toward the target? null if unknown
}

/** points: prior values (most recent last is fine; only the last WINDOW are used,
 *  EXCLUDING the current swing). current: this swing's value. target/direction:
 *  for the toward/away color (null target -> towardPro null). */
export function computeTrend(
  points: { value: number }[],
  current: number,
  target: number | null,
  direction: MetricDirection | null,
): Trend {
  const prior = points.slice(-WINDOW);
  if (prior.length === 0) return { delta: 0, towardPro: null };
  const avg = prior.reduce((s, p) => s + p.value, 0) / prior.length;
  const delta = Math.round((current - avg) * 100) / 100;
  if (target == null || direction == null) return { delta, towardPro: null };

  const dist = (v: number) => {
    if (direction === "higher") return Math.max(0, target - v);
    if (direction === "lower") return Math.max(0, v - target);
    return Math.abs(v - target); // match, range
  };
  if (delta === 0) return { delta, towardPro: null };
  return { delta, towardPro: dist(current) < dist(avg) };
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/frontend`): `npm test -- trend`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/lib/trend.ts web/frontend/src/lib/trend.test.ts
git commit -m "feat(frontend): rolling-average trend with toward/away-from-pro color"
```

---

### Task 9: Phase-from-time util

**Files:**
- Create: `web/frontend/src/lib/phase.ts`
- Test: `web/frontend/src/lib/phase.test.ts`

- [ ] **Step 1: Write the failing test**

```typescript
// web/frontend/src/lib/phase.test.ts
import { describe, it, expect } from "vitest";
import { phaseAtTime, phaseMoments } from "./phase";
import type { Moment } from "./types";

const m = (kind: string, time_s: number): Moment =>
  ({ id: 0, swing_id: 1, kind, view: null, frame_index: null, time_s });

describe("phaseAtTime", () => {
  const moments = [m("address", 0), m("top", 1.0), m("impact", 1.5)];
  it("returns the latest phase whose time <= t", () => {
    expect(phaseAtTime(moments, 0.5)).toBe("address");
    expect(phaseAtTime(moments, 1.2)).toBe("top");
    expect(phaseAtTime(moments, 2.0)).toBe("impact");
  });
  it("before the first moment -> the first phase", () => {
    expect(phaseAtTime(moments, -1)).toBe("address");
  });
  it("no card-phase moments -> defaults to impact", () => {
    expect(phaseAtTime([], 0)).toBe("impact");
  });
  it("phaseMoments keeps only address/top/impact, time-ordered", () => {
    const out = phaseMoments([m("impact", 1.5), m("takeaway", 0.3), m("top", 1.0), m("address", 0)]);
    expect(out.map((x) => x.kind)).toEqual(["address", "top", "impact"]);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/frontend`): `npm test -- phase`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `phase.ts`**

```typescript
// web/frontend/src/lib/phase.ts
import type { Moment } from "./types";
import { PHASES, type Phase } from "./metricConfig";

/** Keep only the card phases (address/top/impact) that have a timestamp, ordered. */
export function phaseMoments(moments: Moment[]): Moment[] {
  return PHASES
    .map((p) => moments.find((m) => m.kind === p && m.time_s != null))
    .filter((m): m is Moment => !!m);
}

/** The current card phase at playback time t = the latest card-phase moment whose
 *  time_s <= t. Falls back to the first available phase, or "impact" if none. */
export function phaseAtTime(moments: Moment[], t: number): Phase {
  const pm = phaseMoments(moments);
  if (pm.length === 0) return "impact";
  let current = pm[0];
  for (const mt of pm) {
    if ((mt.time_s as number) <= t) current = mt;
  }
  return current.kind as Phase;
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/frontend`): `npm test -- phase`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/lib/phase.ts web/frontend/src/lib/phase.test.ts
git commit -m "feat(frontend): phaseAtTime util mapping playback time -> swing phase"
```

---

## TASK GROUP C — FRONTEND COMPONENTS

### Task 10: Rewrite `MetricCard` (combined Layout-A card)

**Files:**
- Rewrite: `web/frontend/src/components/MetricCard.tsx`
- Test: `web/frontend/src/components/MetricCard.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/frontend/src/components/MetricCard.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "./MetricCard";

describe("MetricCard", () => {
  it("benchmarked: shows value, tour line, delta", () => {
    render(<MetricCard label="Shoulder Tilt" phase="top" value={38} unit="deg"
      target={36} delta={2} zone="green" state="ok"
      trend={{ delta: 1.2, towardPro: true }} />);
    expect(screen.getByText("38")).toBeInTheDocument();
    expect(screen.getByText(/Tour 36/)).toBeInTheDocument();
  });
  it("needs_3d: shows NEEDS 3D, no delta", () => {
    render(<MetricCard label="Shoulder Turn" phase="top" value={84} unit="deg"
      target={89} delta={null} zone={null} state="needs_3d"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/NEEDS 3D/)).toBeInTheDocument();
  });
  it("raw: shows no tour avg", () => {
    render(<MetricCard label="Hand Depth" phase="impact" value={9.2} unit="in"
      target={null} delta={null} zone={null} state="raw"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/no tour avg/i)).toBeInTheDocument();
  });
  it("off-phase: dims with '— measured at'", () => {
    render(<MetricCard label="Early Ext." value={null} unit="in"
      target={0} delta={null} zone={null} state="ok" offPhase="impact"
      trend={{ delta: 0, towardPro: null }} />);
    expect(screen.getByText(/measured at impact/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/frontend`): `npm test -- MetricCard`
Expected: FAIL (new props/markup not present).

- [ ] **Step 3: Rewrite `MetricCard.tsx`**

```tsx
import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import { cn } from '../lib/utils'
import { motion } from 'framer-motion'
import type { MetricZone, MetricState } from '../lib/types'

const ZONE_ACCENT: Record<MetricZone, string> = {
  green: 'border-l-garage-green',
  yellow: 'border-l-[#E8B931]',
  red: 'border-l-garage-red',
}
const ZONE_TEXT: Record<MetricZone, string> = {
  green: 'text-garage-green',
  yellow: 'text-[#E8B931]',
  red: 'text-garage-red',
}

export interface MetricCardTrend { delta: number; towardPro: boolean | null }

export interface MetricCardProps {
  label: string
  value: number | null
  unit: string
  target: number | null
  delta: number | null
  zone: MetricZone | null
  state: MetricState
  trend: MetricCardTrend
  phase?: string          // inline phase badge (body cards)
  offPhase?: string       // when set, card is dimmed: "— measured at <offPhase>"
  isEstimated?: boolean
  highlight?: boolean
}

function fmt(v: number, unit: string) {
  const r = unit === 'rpm' ? Math.round(v) : Math.round(v * 10) / 10
  return unit === 'deg' ? `${r}°` : unit === 'in' ? `${r}"` : unit ? `${r} ${unit}` : `${r}`
}

export function MetricCard({
  label, value, unit, target, delta, zone, state, trend,
  phase, offPhase, isEstimated, highlight,
}: MetricCardProps) {
  // Off-phase: dimmed placeholder, grid stays stable.
  if (offPhase || value == null) {
    return (
      <div className="bg-[#0E1210] border border-dashed border-[#242C27] rounded-[18px] p-5 opacity-50 flex flex-col">
        <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold">{label}</span>
        <span className="mt-3 text-sm text-[#8B978F]">
          {offPhase ? `— measured at ${offPhase}` : '—'}
        </span>
      </div>
    )
  }

  const accent = state === 'ok' && zone ? ZONE_ACCENT[zone] : 'border-l-[#4A554E]'
  const deltaColor = state === 'ok' && zone ? ZONE_TEXT[zone] : 'text-[#8B978F]'
  const trendColor =
    trend.towardPro == null ? 'text-[#8B978F]'
      : trend.towardPro ? 'text-garage-green' : 'text-garage-red'

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
      className={cn(
        'bg-[#121714] border border-[#242C27] border-l-4 rounded-[18px] p-4 flex flex-col transition-all duration-300',
        accent, highlight && 'shadow-glow-primary-sm',
      )}
    >
      <div className="flex justify-between items-center">
        <span className="flex items-center gap-2">
          <span className="text-[10px] uppercase tracking-[0.1em] text-[#8B978F] font-semibold">{label}</span>
          {phase && (
            <span className="text-[9px] uppercase tracking-wider text-[#8B978F] bg-[#1A211D] px-1.5 py-0.5 rounded">{phase}</span>
          )}
          {isEstimated && (
            <span className="text-[9px] text-[#8B978F]">~est</span>
          )}
        </span>
        {trend.delta !== 0 ? (
          <span className={cn('flex items-center text-xs font-medium', trendColor)}>
            {trend.delta > 0 ? <ArrowUpRight className="w-3 h-3 mr-0.5" /> : <ArrowDownRight className="w-3 h-3 mr-0.5" />}
            {Math.abs(trend.delta)}
          </span>
        ) : (
          <span className="flex items-center text-xs text-[#8B978F]"><Minus className="w-3 h-3 mr-0.5" />0</span>
        )}
      </div>

      <div className="mt-2 flex items-baseline gap-1">
        <span className="text-3xl font-bold font-mono tracking-tight text-[#E7EEE9]">
          {unit === 'rpm' ? Math.round(value) : Math.round(value * 10) / 10}
        </span>
        <span className="text-sm text-[#8B978F]">{unit === 'deg' ? '°' : unit === 'in' ? 'in' : unit}</span>
      </div>

      <div className="mt-1 text-xs font-mono text-[#8B978F]">
        {state === 'raw' ? (
          <span>no tour avg</span>
        ) : state === 'needs_3d' ? (
          <span className="bg-[#1A211D] px-1.5 py-0.5 rounded">NEEDS 3D · tour {target}</span>
        ) : (
          <>Tour {target != null ? fmt(target, unit) : '—'}{' '}
            {delta != null && <span className={deltaColor}>· {delta >= 0 ? '+' : ''}{fmt(delta, unit)}</span>}
          </>
        )}
      </div>
    </motion.div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/frontend`): `npm test -- MetricCard`
Expected: PASS (4 tests).

> Note: callers of the old `MetricCard` (LiveScreen) will not typecheck until Task 13. That's expected; the build is fixed there.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/MetricCard.tsx web/frontend/src/components/MetricCard.test.tsx
git commit -m "feat(frontend): rebuild MetricCard as combined you-vs-pro stoplight card"
```

---

### Task 11: Extract `PhaseTimeline`

**Files:**
- Create: `web/frontend/src/components/PhaseTimeline.tsx`
- Test: `web/frontend/src/components/PhaseTimeline.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/frontend/src/components/PhaseTimeline.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PhaseTimeline } from "./PhaseTimeline";

describe("PhaseTimeline", () => {
  it("renders the 8 phases and marks present ones, fires onSeek with the kind", () => {
    const onSeek = vi.fn();
    render(<PhaseTimeline present={new Set(["Address", "Top", "Impact"])}
      active="Top" onSeek={onSeek} />);
    expect(screen.getByText("Address")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Impact"));
    expect(onSeek).toHaveBeenCalledWith("Impact");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/frontend`): `npm test -- PhaseTimeline`
Expected: FAIL (module not found).

- [ ] **Step 3: Create `PhaseTimeline.tsx`** (extracted from the inline timeline in `ReviewScreen.tsx`, made reusable)

```tsx
import { cn } from '../lib/utils'

export const PHASE_LABELS = [
  'Address', 'Takeaway', 'Lead-arm', 'Top',
  'Transition', 'Shaft par.', 'Impact', 'Follow-thru',
] as const

interface PhaseTimelineProps {
  present: Set<string>          // labels that have a moment (clickable)
  active: string                // currently active label
  onSeek: (label: string) => void
}

export function PhaseTimeline({ present, active, onSeek }: PhaseTimelineProps) {
  return (
    <div className="relative pt-4 pb-2 px-4">
      <div className="absolute top-6 left-8 right-8 h-0.5 bg-[#242C27]" />
      <div className="flex justify-between relative">
        {PHASE_LABELS.map((phase) => {
          const isActive = active === phase
          const exists = present.has(phase)
          return (
            <button
              key={phase}
              onClick={() => exists && onSeek(phase)}
              disabled={!exists}
              className="flex flex-col items-center space-y-3 group disabled:cursor-default"
            >
              <div className={cn(
                'w-4 h-4 rounded-full border-2 z-10 transition-all',
                isActive ? 'bg-garage-green border-garage-green shadow-glow-primary-sm scale-125'
                  : exists ? 'bg-[#121714] border-garage-green/60 group-hover:border-garage-green'
                    : 'bg-[#121714] border-[#4A554E]',
              )} />
              <span className={cn(
                'text-[10px] uppercase tracking-wider font-medium transition-colors',
                isActive ? 'text-garage-green' : exists ? 'text-[#8B978F] group-hover:text-[#E7EEE9]' : 'text-[#4A554E]',
              )}>{phase}</span>
            </button>
          )
        })}
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/frontend`): `npm test -- PhaseTimeline`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/PhaseTimeline.tsx web/frontend/src/components/PhaseTimeline.test.tsx
git commit -m "feat(frontend): shared PhaseTimeline component"
```

---

### Task 12: Rewrite `SwingReplay` as a real video

**Files:**
- Rewrite: `web/frontend/src/components/SwingReplay.tsx`
- Test: `web/frontend/src/components/SwingReplay.test.tsx`

- [ ] **Step 1: Write the failing test** (jsdom doesn't play video; assert structure + controlled behavior)

```tsx
// web/frontend/src/components/SwingReplay.test.tsx
import { describe, it, expect } from "vitest";
import { render } from "@testing-library/react";
import { SwingReplay } from "./SwingReplay";

describe("SwingReplay", () => {
  it("renders a <video> with the source when src is provided", () => {
    const { container } = render(<SwingReplay src="/media/swings/x.mp4" />);
    const video = container.querySelector("video");
    expect(video).not.toBeNull();
    expect(video?.getAttribute("src")).toBe("/media/swings/x.mp4");
  });
  it("falls back to the placeholder when no src", () => {
    const { container } = render(<SwingReplay src={null} />);
    expect(container.querySelector("video")).toBeNull();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/frontend`): `npm test -- SwingReplay`
Expected: FAIL (current SwingReplay has no `<video>` / no `src` prop).

- [ ] **Step 3: Rewrite `SwingReplay.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react'
import { Play, Pause, Maximize2 } from 'lucide-react'
import { cn } from '../lib/utils'

interface SwingReplayProps {
  src?: string | null            // annotated video URL; null -> placeholder
  highlight?: boolean
  seekTo?: number | null         // when this changes, seek the video to it (seconds)
  onTime?: (t: number) => void   // playback time (seconds), for phase sync
}

export function SwingReplay({ src, highlight, seekTo, onTime }: SwingReplayProps) {
  const ref = useRef<HTMLVideoElement>(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [speed, setSpeed] = useState<'realtime' | 'slowmo'>('realtime')
  const [progress, setProgress] = useState(0)

  // Controlled seek from the PhaseTimeline.
  useEffect(() => {
    const v = ref.current
    if (v && seekTo != null && Number.isFinite(seekTo)) {
      v.currentTime = seekTo
    }
  }, [seekTo])

  useEffect(() => {
    const v = ref.current
    if (v) v.playbackRate = speed === 'slowmo' ? 0.25 : 1
  }, [speed])

  const toggle = () => {
    const v = ref.current
    if (!v) return
    if (v.paused) { v.play(); setIsPlaying(true) }
    else { v.pause(); setIsPlaying(false) }
  }

  const onTimeUpdate = () => {
    const v = ref.current
    if (!v) return
    onTime?.(v.currentTime)
    setProgress(v.duration ? (v.currentTime / v.duration) * 100 : 0)
  }

  return (
    <div className={cn(
      'relative w-full h-full bg-[#0A0D0B] rounded-[18px] overflow-hidden border flex flex-col',
      highlight ? 'border-garage-green shadow-glow-primary' : 'border-[#242C27]',
    )}>
      <div className="flex-1 relative bg-gradient-to-b from-[#121714] to-[#0A0D0B] flex items-center justify-center">
        {src ? (
          <video ref={ref} src={src} onTimeUpdate={onTimeUpdate}
            onEnded={() => setIsPlaying(false)} playsInline
            className="w-full h-full object-contain" />
        ) : (
          <div className="text-[#8B978F] text-sm">No swing video yet.</div>
        )}
        <div className="absolute top-4 right-4 flex space-x-2">
          <div className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-1 border border-[#242C27] flex">
            {(['realtime', 'slowmo'] as const).map((s) => (
              <button key={s} onClick={() => setSpeed(s)}
                className={cn('px-3 py-1 rounded-full text-xs font-medium transition-colors',
                  speed === s ? 'bg-[#242C27] text-[#E7EEE9]' : 'text-[#8B978F] hover:text-[#E7EEE9]')}>
                {s === 'realtime' ? 'Realtime' : 'Slow-mo'}
              </button>
            ))}
          </div>
          <button className="bg-[#0A0D0B]/80 backdrop-blur rounded-full p-2 border border-[#242C27] text-[#8B978F]">
            <Maximize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="h-16 bg-[#121714] border-t border-[#242C27] px-6 flex items-center space-x-4">
        <button onClick={toggle} disabled={!src}
          className="w-10 h-10 rounded-full bg-garage-green text-[#0A0D0B] flex items-center justify-center disabled:opacity-40 flex-shrink-0">
          {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
        </button>
        <div className="flex-1 h-2 bg-[#1A211D] rounded-full relative">
          <div className="absolute top-0 left-0 h-full bg-garage-green rounded-full shadow-glow-primary-sm"
            style={{ width: `${progress}%` }} />
        </div>
      </div>
    </div>
  )
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/frontend`): `npm test -- SwingReplay`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/SwingReplay.tsx web/frontend/src/components/SwingReplay.test.tsx
git commit -m "feat(frontend): SwingReplay plays real annotated video, emits time, controlled seek"
```

---

## TASK GROUP D — SCREENS

### Task 13: Rework `LiveScreen` (cards + phase jumper)

**Files:**
- Modify: `web/frontend/src/pages/LiveScreen.tsx`
- Helper to build card view-models: inline in `LiveScreen` (kept small) or a shared
  `lib/cards.ts`. This plan inlines it; extract later if Review needs the same body grid.

- [ ] **Step 1: Replace `LiveScreen.tsx`**

```tsx
import { useEffect, useMemo, useState } from 'react'
import { SwingReplay } from '../components/SwingReplay'
import { MetricCard } from '../components/MetricCard'
import { AIInsightCard } from '../components/AIInsightCard'
import { ClubSelector } from '../components/ClubSelector'
import { PhaseTimeline } from '../components/PhaseTimeline'
import { motion, AnimatePresence } from 'framer-motion'
import { useApi } from '../lib/useApi'
import { getLatestSwing, getHistory, mediaUrl } from '../lib/api'
import { labelFor, coachingToInsights, isEstimated } from '../lib/format'
import { BODY_CARD_ORDER, BALL_BENCHMARK_ORDER, BALL_RAW_ORDER, METRIC_UNIT } from '../lib/metricConfig'
import { phaseAtTime, phaseMoments } from '../lib/phase'
import { computeTrend } from '../lib/trend'
import type { SwingDetail, Benchmark, BallBenchmark, BallRawField } from '../lib/types'

const CAP = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

interface LiveScreenProps {
  playerId: number | null
  sessionId: number | null
  lastSwing: unknown
  lastCapture: unknown
  activeClub?: string | null
  onSelectClub?: (club: string | null) => void
}

export function LiveScreen({ playerId, sessionId, lastSwing, activeClub = null, onSelectClub }: LiveScreenProps) {
  const { data, error, reload } = useApi<SwingDetail | null>(
    () => (playerId ? getLatestSwing(playerId, sessionId ?? undefined) : Promise.resolve(null)),
    [playerId, sessionId],
  )
  useEffect(() => { reload() }, [lastSwing]) // eslint-disable-line react-hooks/exhaustive-deps

  // Current phase, driven by the replay playhead (default impact).
  const [videoTime, setVideoTime] = useState(0)
  const [seekTo, setSeekTo] = useState<number | null>(null)
  const moments = data?.moments ?? []
  const currentPhase = phaseAtTime(moments, videoTime)

  // Trend history per body metric@phase (fetched once per swing).
  const swingId = data?.swing.id ?? null
  const { data: histories } = useApi<Record<string, { value: number }[]>>(
    async () => {
      if (!playerId || !swingId) return {}
      const entries = await Promise.all(
        BODY_CARD_ORDER.map(async (name) => {
          const h = await getHistory(playerId, name, currentPhase).catch(() => ({ points: [] }))
          return [name, (h.points ?? []).slice(0, -1)] as const  // exclude current swing
        }),
      )
      return Object.fromEntries(entries)
    },
    [playerId, swingId, currentPhase],
  )

  const annotated = data?.media?.find((m) => m.kind === 'annotated_video')
  const videoSrc = annotated ? mediaUrl(annotated.path) : null

  // Index benchmark rows by name+context.
  const benchByKey = useMemo(() => {
    const map = new Map<string, Benchmark>()
    for (const b of data?.benchmarks ?? []) map.set(`${b.name}|${b.context}`, b)
    return map
  }, [data])

  const coachContent = data?.coaching[0]?.content ?? null
  const insights = coachingToInsights(coachContent)
  const status: 'waiting' | 'captured' = data ? 'captured' : 'waiting'

  const present = new Set(phaseMoments(moments).map((m) => CAP(m.kind)))

  return (
    <div className="h-full flex flex-col p-6 space-y-6 overflow-y-auto">
      {error && (
        <div className="rounded-[18px] border border-garage-red/40 bg-garage-red/10 px-6 py-4 text-sm text-garage-red">
          Failed to load live data: {error}
        </div>
      )}
      {onSelectClub && <ClubSelector value={activeClub} onChange={onSelectClub} />}

      <AnimatePresence mode="wait">
        {status === 'waiting' ? (
          <motion.div key="waiting" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50">
            <div className="w-16 h-16 rounded-full bg-[#121714] border border-[#242C27] flex items-center justify-center mb-6 relative">
              <div className="absolute inset-0 rounded-full border-2 border-garage-green animate-ping opacity-20" />
              <div className="w-3 h-3 rounded-full bg-garage-green animate-pulse" />
            </div>
            <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">Waiting for your R50</h2>
            <p className="text-[#8B978F]">Step up and take a swing. Data will appear here automatically.</p>
          </motion.div>
        ) : (
          <motion.div key="captured" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex-1 flex flex-col space-y-6">
            {/* Replay + phase jumper + coach */}
            <div className="flex flex-col lg:flex-row gap-6">
              <div className="flex-[2] flex flex-col">
                <div className="h-[360px]">
                  <SwingReplay src={videoSrc} highlight seekTo={seekTo} onTime={setVideoTime} />
                </div>
                <PhaseTimeline present={present} active={CAP(currentPhase)}
                  onSeek={(label) => {
                    const mt = moments.find((m) => CAP(m.kind) === label)
                    if (mt?.time_s != null) setSeekTo(mt.time_s)
                  }} />
              </div>
              <div className="flex-1">
                <AIInsightCard headline={coachContent?.headline ?? 'No coaching available yet.'}
                  insights={insights} highlight />
              </div>
            </div>

            {/* BODY cards */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-semibold text-[#E7EEE9]">Body Mechanics · vs Tour Pro</span>
                <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">{currentPhase}</span>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
                {BODY_CARD_ORDER.map((name) => {
                  const b = benchByKey.get(`${name}|${currentPhase}`)
                  const unit = b?.unit ?? METRIC_UNIT[name] ?? ''
                  if (!b) {
                    return <MetricCard key={name} label={labelFor(name)} value={null} unit={unit}
                      target={null} delta={null} zone={null} state="raw" offPhase={currentPhase}
                      trend={{ delta: 0, towardPro: null }} />
                  }
                  const trend = computeTrend(histories?.[name] ?? [], b.value, b.target, b.direction)
                  return <MetricCard key={name} label={labelFor(name)} phase={currentPhase}
                    value={b.value} unit={b.unit ?? unit} target={b.target} delta={b.delta}
                    zone={b.zone} state={b.state} trend={trend} isEstimated={isEstimated(null)} />
                })}
              </div>
            </div>

            {/* BALL cards */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <span className="text-sm font-semibold text-[#E7EEE9]">Ball &amp; Club · vs Tour Pro</span>
                <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
                  {activeClub ? `${activeClub} · impact` : 'select club'}
                </span>
              </div>
              <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
                {(() => {
                  const bench = new Map((data?.ball_benchmarks ?? []).map((b: BallBenchmark) => [b.key, b]))
                  const raw = new Map((data?.ball_raw ?? []).map((r: BallRawField) => [r.key, r]))
                  const cards = []
                  for (const key of BALL_BENCHMARK_ORDER) {
                    const b = bench.get(key); if (!b) continue
                    cards.push(<MetricCard key={key} label={b.label} value={b.value} unit={b.unit}
                      target={b.target} delta={b.delta} zone={b.zone} state="ok"
                      trend={{ delta: 0, towardPro: null }} />)
                  }
                  for (const key of BALL_RAW_ORDER) {
                    const r = raw.get(key); if (!r || r.value == null) continue
                    cards.push(<MetricCard key={key} label={r.label} value={r.value} unit={r.unit}
                      target={null} delta={null} zone={null} state="raw"
                      trend={{ delta: 0, towardPro: null }} />)
                  }
                  return cards.length ? cards
                    : <p className="text-sm text-[#8B978F] col-span-full">No matched ball data yet.</p>
                })()}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
```

> Ball trend arrows: left neutral here for the first pass (ball history is per-club via `/api/ball-history`; wiring it into the card is a follow-up — see Task 16). Body trends are wired.

- [ ] **Step 2: Typecheck/build**

Run (from `web/frontend`): `npm run build`
Expected: PASS (no type errors). Fix any import/prop mismatches.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/pages/LiveScreen.tsx
git commit -m "feat(live): body+ball stoplight cards, replay-driven phase, phase jumper"
```

---

### Task 14: Rework `ReviewScreen` (table colored vs tour + ball cards)

**Files:**
- Modify: `web/frontend/src/pages/ReviewScreen.tsx`

- [ ] **Step 1: Update `ReviewScreen.tsx`**

Replace the imports block + the metric-table rendering + the bottom ball panel. Key changes:
(a) build a `Map<name|context, Benchmark>` from `data.benchmarks`; (b) render each cell from it with zone color; (c) replace `BallBenchmarkPanel`/`BallClubStrip` bottom block with the same MetricCard ball grid as Live; (d) reuse `PhaseTimeline` (extracted) instead of the inline timeline.

```tsx
// --- imports (add/replace) ---
import { MetricCard } from '../components/MetricCard'
import { PhaseTimeline } from '../components/PhaseTimeline'
import { BALL_BENCHMARK_ORDER, BALL_RAW_ORDER, BODY_CARD_ORDER } from '../lib/metricConfig'
import { labelFor } from '../lib/format'
import type { Benchmark } from '../lib/types'
// keep existing: useState/useEffect, SwingReplay, AIInsightCard, useApi, getSwing, getSwings, types

// --- zone color helper (module scope) ---
const ZONE_TEXT: Record<string, string> = {
  green: 'text-garage-green', yellow: 'text-[#E8B931]', red: 'text-garage-red',
}
```

In the component body, build the lookup and the rows from `BODY_CARD_ORDER`:

```tsx
  const benchByKey = new Map<string, Benchmark>()
  for (const b of data.benchmarks ?? []) benchByKey.set(`${b.name}|${b.context}`, b)

  const cell = (name: string, context: string) => {
    const b = benchByKey.get(`${name}|${context}`)
    if (!b) return <span className="text-[#4A554E]">—</span>
    const color = b.state === 'ok' && b.zone ? ZONE_TEXT[b.zone] : 'text-[#E7EEE9]'
    const sub = b.state === 'raw' ? 'no tour avg'
      : b.state === 'needs_3d' ? `needs 3D · tour ${b.target}`
        : `${b.delta != null && b.delta >= 0 ? '+' : ''}${b.delta} · tour ${b.target}`
    return (
      <span>
        <span className={color}>{b.value}{b.unit === 'deg' ? '°' : b.unit === 'in' ? '"' : ''}</span>
        <span className="block text-[9px] text-[#8B978F]">{sub}</span>
      </span>
    )
  }
```

Replace the table `<tbody>` rows with a row per body metric:

```tsx
  <tbody className="divide-y divide-[#242C27]/50">
    {BODY_CARD_ORDER.map((name) => (
      <tr key={name} className="hover:bg-[#1A211D]/50 transition-colors">
        <td className="py-3 text-sm font-medium text-[#E7EEE9]">{labelFor(name)}</td>
        <td className="py-3 text-sm font-mono">{cell(name, 'address')}</td>
        <td className="py-3 text-sm font-mono">{cell(name, 'top')}</td>
        <td className="py-3 text-sm font-mono">{cell(name, 'impact')}</td>
      </tr>
    ))}
  </tbody>
```

(Remove the old `Status` column header + the `statusFor`/`fmtMetric`/`rows` logic that fed it; the cell coloring replaces it.)

Replace the bottom "Matched R50 Data" + `BallBenchmarkPanel` block with the ball MetricCard grid:

```tsx
  <div className="mt-auto">
    <div className="flex items-center gap-2 mb-3">
      <span className="text-sm font-semibold text-[#E7EEE9]">Ball &amp; Club · vs Tour Pro</span>
      <span className="text-[10px] uppercase tracking-wider text-[#8B978F]">
        {data.shot?.club ? `${data.shot.club} · impact` : 'no matched shot'}
      </span>
    </div>
    <div className="grid grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-2">
      {(() => {
        const bench = new Map((data.ball_benchmarks ?? []).map((b) => [b.key, b]))
        const raw = new Map((data.ball_raw ?? []).map((r) => [r.key, r]))
        const cards: JSX.Element[] = []
        for (const key of BALL_BENCHMARK_ORDER) {
          const b = bench.get(key); if (!b) continue
          cards.push(<MetricCard key={key} label={b.label} value={b.value} unit={b.unit}
            target={b.target} delta={b.delta} zone={b.zone} state="ok"
            trend={{ delta: 0, towardPro: null }} />)
        }
        for (const key of BALL_RAW_ORDER) {
          const r = raw.get(key); if (!r || r.value == null) continue
          cards.push(<MetricCard key={key} label={r.label} value={r.value} unit={r.unit}
            target={null} delta={null} zone={null} state="raw"
            trend={{ delta: 0, towardPro: null }} />)
        }
        return cards.length ? cards : <p className="text-sm text-[#8B978F] col-span-full">No matched ball data.</p>
      })()}
    </div>
  </div>
```

Swap the inline 8-phase timeline for the shared component (drives `activePhase` and seeks the replay):

```tsx
  <PhaseTimeline
    present={new Set(data.moments.map((m) => m.kind === 'address' ? 'Address' : m.kind === 'top' ? 'Top' : m.kind === 'impact' ? 'Impact' : m.kind))}
    active={activePhase}
    onSeek={setActivePhase} />
```

- [ ] **Step 2: Build**

Run (from `web/frontend`): `npm run build`
Expected: PASS. Remove now-unused imports (`BenchmarkPanel`, `BallBenchmarkPanel`, `BallClubStrip`, `statusFor`, `fmtMetric`) to clear lint/TS errors.

- [ ] **Step 3: Commit**

```bash
git add web/frontend/src/pages/ReviewScreen.tsx
git commit -m "feat(review): table cells colored vs tour + ball stoplight cards"
```

---

## TASK GROUP E — VERIFY

### Task 15: Full build, tests, browser verification

- [ ] **Step 1: Backend suite**

Run: `& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Frontend tests + build**

Run (from `web/frontend`): `npm test` then `npm run build`
Expected: all vitest pass; build clean.

- [ ] **Step 3: Reseed + run app, screenshot Live & Review**

```bash
# stop any server on 8000, then:
& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m web.backend.seed_dev
& "C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe" -m uvicorn web.backend.app:app --port 8000
```
Open http://localhost:8000 → Live (cards render, phase badge, tap a phase on the jumper) and Review (table colored, ball cards). Confirm console is clean.

> Seed note: seed swings have no real annotated video file, so SwingReplay shows the "No swing video yet" placeholder and cards default to the **impact** phase — expected. The jumper is exercised against real moments. Verify against a real captured swing once the bay exists.

- [ ] **Step 4: Commit any seed/polish fixes**

```bash
git add -A
git commit -m "chore: polish + verification fixes for vs-pro cards"
```

---

### Task 16 (follow-up, optional): Ball trend arrows per club

Wire `/api/ball-history` (already built) into the ball MetricCards so they show a trend arrow vs the rolling average for the active club, mirroring the body trend. Deferred from Task 13/14 to keep the first pass focused; the card already supports `trend`.

- [ ] Fetch `getBallHistory(playerId, key, club)` per ball metric, slice to recent window, `computeTrend(points, value, target, direction)`, pass into the ball `MetricCard`s. Commit.

---

## Self-Review (completed by plan author)

- **Spec coverage:** §3 inventory → Tasks 2,3,4,7 (refs + card lists). §4 thresholds → Task 1. §5 trend → Task 8 + wired in 13 (body) / 16 (ball). §6 card states → Task 10. §7 replay+phase → Tasks 9,11,12,13. §8 layout → Tasks 13,14. §9 backend → Tasks 1–5. §10 components → Tasks 10–12. §11 testing → tests in every task + Task 15. HLA surfacing → Task 4. ✓
- **Placeholders:** none — every code step has full code; the only deferral (ball trend arrows) is an explicit, optional follow-up (Task 16) with the card already supporting it.
- **Type consistency:** `zone_for`/`direction_for` (Task 1) used by Tasks 3,4; `Benchmark`/`BallBenchmark` fields (Task 6) consumed in 10,13,14; `computeTrend` signature (Task 8) matches calls in 13; `phaseAtTime`/`phaseMoments` (Task 9) match usage in 13; `MetricCardProps` (Task 10) match call sites in 13,14; `PhaseTimeline` props (Task 11) match 13,14; `SwingReplay` props (Task 12) match 13.
