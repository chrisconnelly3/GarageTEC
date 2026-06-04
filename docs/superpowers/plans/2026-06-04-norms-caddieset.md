# Populate AI-Coach Norms from CaddieSet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the placeholder `coach/norms/norms.json` with real, cited per-phase "typical range" bands derived honestly from the CaddieSet dataset — only where CaddieSet's metric definition genuinely matches ours — produced by a reproducible generator, with honest `confidence` flags (most of our metrics get `confidence:"none"` and fall back to player history).

**Architecture:** Vendor `CaddieSet.csv` into the repo (with MIT attribution). A deterministic generator `coach/norms/build_norms.py` loads the CSV, cleans it (drop `inf`/`NaN`, drop `0.0`/`180.0` clamp artifacts, winsorize extreme outliers), computes p10/median/p90 per *mapped* CaddieSet feature × event, applies axis/unit conversions, and emits `coach/norms/norms.json` matching the exact schema `coach/norms.py` already consumes. Only **2 of our 9 metrics** (`shoulder_tilt_deg`, `spine_angle_deg`) map to CaddieSet; the other **7 are `confidence:"none"`** with documented reasons. Cleaning + percentile + conversion math are TDD'd on tiny synthetic CSVs; the full `norms.json` is a build artifact (run the generator against the vendored CSV), not a hand-written blob.

**Tech Stack:** Python 3.12 (stdlib only — `csv`, `json`, `math`, `statistics`; **no pandas/numpy**), pytest. Python interpreter (py launcher NOT on PATH): `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe` (referred to below as `<PY>`).

---

## Background: the mapping (read before coding)

This is the crux of the work. The mapping was derived by comparing **both** definitions feature-by-feature. Do not change it without re-reading both sides (`metrics/defs/*.py` and the CaddieSet README metric definitions).

### CaddieSet structure (vendored CSV)

- 1,757 shots; 924 `FACEON` rows + 833 `DTL` rows (View column). Each row is one shot by one of 8 golfers (`GolferId`), one club (`ClubType`).
- Per-frame swing features are prefixed by **event index 0–7** = our 8 swing phases:
  - `0` = address, `1` = takeaway, `2` = mid-backswing, `3` = **top**, `4` = transition/early-downswing, `5` = **impact**, `6` = follow-through, `7` = finish.
  - **This event→named-phase index map is an assumption** (standard 8-event golf sequence; CaddieSet README does not name the events). It is recorded in `_meta` as an assumption. We only consume events **0 (address), 3 (top), 5 (impact)** — the named contexts our metrics use.
- Feature definitions that matter (CaddieSet README lines ~28-49):
  - `SHOULDER-ANGLE` = "Shoulder angle **relative to horizontal**" (degrees). **FACEON-only.** Present at events 0,1,2,3,5,6,7.
  - `SPINE-ANGLE` = "Spine angle **relative to horizontal**" (degrees). **DTL-only.** Present at events 0,1,4,5,6,7 — **NOT at event 3 (top).**
  - `UPPER-TILT` = "Lower body to upper body **ratio**" — a ratio, NOT a tilt angle. Do not map.
  - `HIP-ROTATION` = "Rotation degree of pelvis **relative to Address**" (degrees, FACEON). Events 1,2,3,4 — **NOT at event 5 (impact).** Heavy clamp artifacts (98–116 exact `0.0` per event, several exact `180.0`).
  - `HIP-ANGLE` = "Rotation degree of pelvis relative to Address" (degrees, DTL). Events 2,3,4,6,7. Also heavy `0.0` flooding.
  - `HIP-LINE`, `HIP-SHIFTED`, `HEAD-LOC`, `SHOULDER-LOC`, `STANCE-RATIO`, `*-HANGING-BACK` = **normalized positions / ratios**, NOT inches.

### Our 9 metrics (from `metrics/defs/*.py`)

| Our metric | View | Geometry | Unit | Contexts |
|---|---|---|---|---|
| `shoulder_tilt_deg` | face_on | shoulder line angle **vs horizontal** | deg | address, top, impact |
| `hip_tilt_deg` | face_on | hip line angle **vs horizontal** | deg | address, top, impact |
| `spine_angle_deg` | down_line | torso lean **vs vertical** (`atan2(\|dx\|,\|dy\|)`) | deg | address, top, impact |
| `shoulder_turn_deg` | face_on | width foreshortening → rotation (coarse) | deg | top, impact |
| `hip_turn_deg` | face_on | width foreshortening → rotation (coarse) | deg | top, impact |
| `hip_sway_in` | face_on | lateral hip-center displacement (ppi ruler) | in | top, impact, max |
| `head_sway_in` | face_on | lateral head displacement (ppi ruler) | in | top, impact, max |
| `early_extension_in` | down_line | hip forward+vertical shift (ppi ruler) | in | impact, max |
| `hand_depth_in` | down_line | hands-to-trail-shoulder horizontal distance (ppi ruler) | in | top, impact |

### FINAL mapping (locked)

| Our metric × context | CaddieSet feature | Conversion | Confidence | Reason |
|---|---|---|---|---|
| `shoulder_tilt_deg` @ address | `0-SHOULDER-ANGLE` | none (both vs horizontal, deg, FACEON) | **medium** | Same axis/unit/view. Mixed-skill population p10–p90. |
| `shoulder_tilt_deg` @ top | `3-SHOULDER-ANGLE` | none | **medium** | Same. |
| `shoulder_tilt_deg` @ impact | `5-SHOULDER-ANGLE` | none | **medium** | Same. |
| `spine_angle_deg` @ address | `0-SPINE-ANGLE` | `90 - x` (CaddieSet vs horizontal → ours vs vertical) | **medium** | Same axis after conversion, deg, DTL matches our down_line. |
| `spine_angle_deg` @ impact | `5-SPINE-ANGLE` | `90 - x` | **medium** | Same. |
| `spine_angle_deg` @ top | — | — | **none** | CaddieSet has NO `3-SPINE-ANGLE` (DTL) at top. |
| `hip_tilt_deg` (all) | — | — | **none** | CaddieSet has no hip-line-angle-vs-horizontal feature; HIP-LINE/HIP-SHIFTED are displacements, HIP-ROTATION/HIP-ANGLE are rotations. |
| `shoulder_turn_deg` (all) | — | — | **none** | CaddieSet `SHOULDER-ANGLE` is a tilt vs horizontal, not rotation-vs-address; no shoulder-turn feature exists. |
| `hip_turn_deg` (all) | (HIP-ROTATION / HIP-ANGLE considered, REJECTED) | — | **none** | Closest CaddieSet features are pelvis-rotation-vs-address, but: (a) severe clamp artifacts (floods of exact `0.0`, spikes of `180.0`); (b) zero-point/axis not verifiable against our coarse foreshortening estimate; (c) FACEON `HIP-ROTATION` is absent at impact and DTL `HIP-ANGLE` mixes views. Not defensible → none. |
| `hip_sway_in` | — | — | **none** | CaddieSet positional features are normalized ratios, not inches; needs calibration + literature. |
| `head_sway_in` | — | — | **none** | Same unit mismatch (normalized ratios, not inches). |
| `early_extension_in` | — | — | **none** | Same unit mismatch. |
| `hand_depth_in` | — | — | **none** | Same unit mismatch. |

**Result: 2 metrics get real bands** (`shoulder_tilt_deg` at 3 contexts, `spine_angle_deg` at 2 contexts), **7 metrics get `confidence:"none"`.**

### Honesty rules baked into every CaddieSet-derived entry

- `source` MUST read: `"CaddieSet (damilab, MIT) — mixed-skill population p10-p90 typical range, NOT a validated ideal. https://github.com/damilab/CaddieSet"`.
- `confidence` is at most `"medium"` (these are population ranges, not validated good/bad thresholds).
- `units` is `"deg"`.
- No fabricated literature numbers anywhere.

### Schema `coach/norms.py` expects (do not deviate)

`load_norms()` returns the parsed JSON dict. `compare(name, value, club, norms)`:
- `_RESERVED = {"_meta"}` — the `_meta` key is skipped.
- An entry is `{"range": [low, high] | [], "units": str, "source": str|null, "confidence": str, ...}` (extra keys like `comment` are allowed and ignored).
- `confidence == "none"` OR `len(range) != 2` OR `value is None` → history-only result (`in_range=None`, `use_history_only=True`).
- Otherwise compares `value` against `[low, high]`.

`coach/tests/test_norms.py::test_load_norms_has_meta_disclaimer` asserts the loaded JSON has `_meta` and either `_meta["status"]` contains "curated" or `_meta["note"]` contains "human". The new `_meta` MUST satisfy this (keep a "human"/"curated" word in `note` or `status`).

---

## File Structure

- **Create** `coach/norms/data/CaddieSet.csv` — vendored dataset (copied from the upstream clone, unmodified).
- **Create** `coach/norms/data/SOURCE.md` — attribution (CaddieSet, damilab, MIT, URL, citation, vendoring note).
- **Create** `coach/norms/build_norms.py` — the generator: load CSV → clean → percentiles → convert → write `norms.json`. Importable functions (`clean_values`, `percentiles`, `convert`, `build_entries`, `build_meta`, `main`) so the logic is unit-testable.
- **Create** `coach/tests/test_build_norms.py` — TDD tests for cleaning, percentile, conversion, mapping, and the generated-JSON round-trip through `coach.norms`.
- **Create** `coach/tests/fixtures/tiny_caddieset.csv` — tiny synthetic CSV for build tests (hand-built, known values).
- **Modify** `coach/norms/norms.json` — regenerated by running the generator (build artifact, not hand-edited).
- **Modify** (if needed) `coach/tests/test_norms.py::test_load_norms_has_meta_disclaimer` — only if the new `_meta` wording would break it (Task 7 verifies; the new `_meta` is written to keep it passing, so no change is expected).

---

## Task 1: Vendor the CaddieSet CSV + attribution

**Files:**
- Create: `coach/norms/data/CaddieSet.csv`
- Create: `coach/norms/data/SOURCE.md`

- [ ] **Step 1: Clone upstream into a temp dir (outside the repo)**

```bash
git clone --depth 1 https://github.com/damilab/CaddieSet "$TEMP/CaddieSet_src"
```

Expected: clone succeeds; `"$TEMP/CaddieSet_src/data/CaddieSet.csv"` (~508 KB, 1758 lines incl. header) and `"$TEMP/CaddieSet_src/LICENSE"` (MIT) exist.

- [ ] **Step 2: Copy the CSV into the repo, unmodified**

```bash
mkdir -p coach/norms/data
cp "$TEMP/CaddieSet_src/data/CaddieSet.csv" coach/norms/data/CaddieSet.csv
```

Verify the header is intact (first line starts `View,ClubType,Distance,...,0-SHOULDER-ANGLE,...`):

Run: `"<PY>" -c "print(open('coach/norms/data/CaddieSet.csv').readline()[:60])"`
Expected: `View,ClubType,Distance,Carry,LrDistanceOut,DirectionAngle,Spin`

- [ ] **Step 3: Write the attribution file**

Create `coach/norms/data/SOURCE.md` with this exact content:

```markdown
# CaddieSet — vendored dataset

`CaddieSet.csv` in this directory is the official dataset from:

> **CaddieSet: A Golf Swing Dataset with Human Joint Features and Ball Information**
> Jung, Hong, Jeong, Jeong, Choi, Kim, Lee. CVPR 2025 Workshop (CVSPORTS).

- Source: https://github.com/damilab/CaddieSet
- Copyright (c) 2024 damilab. Licensed under the **MIT License** (redistribution
  permitted with attribution — see the MIT terms reproduced below).
- The CSV is vendored **unmodified** from the upstream `data/CaddieSet.csv`.

## Why it is here

`coach/norms/build_norms.py` reads this CSV to compute population "typical range"
bands (p10–median–p90) for the small subset of our metrics whose geometric
definition genuinely matches a CaddieSet feature. These are **mixed-skill
population ranges, NOT validated ideal/good-bad thresholds.** Most of our metrics
cannot be sourced from CaddieSet (unit/axis mismatch) and are left
`confidence:"none"` so the coach falls back to the player's own history.

## Citation

    @inproceedings{jung2025caddieset,
      title={CaddieSet: A Golf Swing Dataset with Human Joint Features and Ball Information},
      author={Jung, Seunghyeon and Hong, Seoyoung and Jeong, Jiwoo and Jeong, Seungwon and Choi, Jaerim and Kim, Hoki and Lee, Woojin},
      booktitle={Proceedings of the Computer Vision and Pattern Recognition Conference},
      pages={5988--5996},
      year={2025}
    }

## MIT License (CaddieSet)

MIT License

Copyright (c) 2024 damilab

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Confirm both files are present and sized**

Run: `"<PY>" -c "import os; print(os.path.getsize('coach/norms/data/CaddieSet.csv') > 400000, os.path.exists('coach/norms/data/SOURCE.md'))"`
Expected: `True True`

- [ ] **Step 5: Commit**

```bash
git add coach/norms/data/CaddieSet.csv coach/norms/data/SOURCE.md
git commit -m "chore(norms): vendor CaddieSet.csv with MIT attribution"
```

---

## Task 2: Cleaning helper — `clean_values()` (TDD)

Cleaning rule (applied to one already-float-parsed list for one feature column):
1. Drop `None`, `inf`, `-inf`, `NaN`.
2. Drop exact clamp artifacts: values equal to `0.0` or `180.0` (CaddieSet's pose-estimator clamp floor/ceiling — confirmed flooding in HIP-ROTATION/HIP-ANGLE and a few in SHOULDER/SPINE). We pass `drop_clamps=(0.0, 180.0)` and drop exact matches.
3. Winsorize extreme outliers: clip to the [1st percentile, 99th percentile] of the *surviving* values (pull tails in, don't delete rows), so a single 123.0 stray cannot move p90.

**Files:**
- Create: `coach/norms/build_norms.py`
- Test: `coach/tests/test_build_norms.py`

- [ ] **Step 1: Write the failing tests**

Create `coach/tests/test_build_norms.py`:

```python
import math

from coach.norms import build_norms as b


def test_clean_drops_inf_nan_and_none():
    raw = [10.0, float("inf"), float("-inf"), float("nan"), None, 12.0]
    out = b.clean_values(raw)
    assert out == [10.0, 12.0]


def test_clean_drops_exact_clamp_artifacts():
    raw = [0.0, 5.0, 180.0, 7.0, 0.0]
    out = b.clean_values(raw, drop_clamps=(0.0, 180.0))
    assert out == [5.0, 7.0]


def test_clean_winsorizes_extreme_outliers_inward():
    # 100 values 1..100; a stray 100000 should be clipped down to the p99 of
    # the surviving set (not deleted), and the tiny -100000 clipped up to p1.
    raw = [float(i) for i in range(1, 101)] + [100000.0, -100000.0]
    out = b.clean_values(raw)
    assert max(out) < 200.0          # huge outlier pulled in
    assert min(out) > -50.0          # huge negative pulled in
    assert len(out) == 102           # winsorize clips, does not drop rows


def test_clean_empty_returns_empty():
    assert b.clean_values([]) == []
    assert b.clean_values([float("nan"), None]) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'coach.norms.build_norms'` (the package dir `coach/norms/` has no `__init__.py` and no module yet).

- [ ] **Step 3: Create the module with the cleaning helper**

Create `coach/norms/build_norms.py`:

```python
"""Generate coach/norms/norms.json from the vendored CaddieSet CSV.

HONEST norms: only metrics whose geometric definition genuinely matches a
CaddieSet feature get a real band (mixed-skill population p10-p90, NOT a
validated ideal). Everything else is confidence:"none" -> the coach falls back
to the player's own history. See coach/norms/data/SOURCE.md for attribution and
the plan doc for the full mapping rationale.

Stdlib only (csv, json, math) — no pandas/numpy.
"""
import csv
import json
import math
import os

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CSV_PATH = os.path.join(DATA_DIR, "CaddieSet.csv")
OUT_PATH = os.path.join(os.path.dirname(__file__), "norms.json")

CLAMP_ARTIFACTS = (0.0, 180.0)


def _percentile(sorted_vals, p):
    """Linear-interpolation percentile, p in [0,1]. sorted_vals must be sorted
    and non-empty."""
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = int(math.floor(k))
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def clean_values(raw, drop_clamps=CLAMP_ARTIFACTS):
    """Drop None/inf/nan, drop exact clamp artifacts, then winsorize the
    survivors to their [p1, p99] (clip tails inward; preserve count)."""
    vals = []
    for v in raw:
        if v is None:
            continue
        f = float(v)
        if math.isinf(f) or math.isnan(f):
            continue
        if any(f == c for c in drop_clamps):
            continue
        vals.append(f)
    if not vals:
        return []
    s = sorted(vals)
    lo = _percentile(s, 0.01)
    hi = _percentile(s, 0.99)
    return [min(max(v, lo), hi) for v in vals]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add coach/norms/build_norms.py coach/tests/test_build_norms.py
git commit -m "feat(norms): cleaning helper for CaddieSet build (drop clamp/inf, winsorize)"
```

---

## Task 3: Percentile band + axis conversion (TDD)

`percentiles(clean_vals)` → `(p10, median, p90)` rounded to 2 decimals, or `None` if the input is empty. `convert(value, kind)` applies the axis conversion: `kind="none"` returns the value unchanged; `kind="vertical_from_horizontal"` returns `90 - value` (CaddieSet spine vs horizontal → ours vs vertical).

**Files:**
- Modify: `coach/norms/build_norms.py`
- Test: `coach/tests/test_build_norms.py`

- [ ] **Step 1: Add the failing tests**

Append to `coach/tests/test_build_norms.py`:

```python
def test_percentiles_basic():
    vals = [float(i) for i in range(1, 101)]  # 1..100
    p10, med, p90 = b.percentiles(vals)
    assert abs(p10 - 10.9) < 0.5
    assert abs(med - 50.5) < 0.5
    assert abs(p90 - 90.1) < 0.5


def test_percentiles_empty_is_none():
    assert b.percentiles([]) is None


def test_convert_none_is_identity():
    assert b.convert(11.16, "none") == 11.16


def test_convert_vertical_from_horizontal():
    # CaddieSet spine 70.53 deg vs horizontal -> 19.47 deg vs vertical (ours)
    assert abs(b.convert(70.53, "vertical_from_horizontal") - 19.47) < 1e-9
```

- [ ] **Step 2: Run to verify they fail**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'percentiles'`.

- [ ] **Step 3: Implement `percentiles` and `convert`**

Append to `coach/norms/build_norms.py`:

```python
def percentiles(clean_vals):
    """Return (p10, median, p90) rounded to 2 dp, or None if empty."""
    if not clean_vals:
        return None
    s = sorted(clean_vals)
    return (round(_percentile(s, 0.10), 2),
            round(_percentile(s, 0.50), 2),
            round(_percentile(s, 0.90), 2))


def convert(value, kind):
    """Axis/unit conversion for one value.
    'none'                     -> identity (same axis & units).
    'vertical_from_horizontal' -> 90 - value (CaddieSet vs horizontal -> ours
                                  vs vertical).
    """
    if kind == "none":
        return value
    if kind == "vertical_from_horizontal":
        return 90.0 - value
    raise ValueError(f"unknown conversion kind: {kind!r}")
```

- [ ] **Step 4: Run to verify they pass**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
git add coach/norms/build_norms.py coach/tests/test_build_norms.py
git commit -m "feat(norms): percentile band + axis conversion helpers"
```

---

## Task 4: The mapping table + `build_entries()` over a synthetic CSV (TDD)

This is the heart of the generator: read the CSV, and for **each mapped (our_metric, context) pair** pull the right CaddieSet column, clean it, optionally convert each value, compute the band, and emit a per-metric entry. When a conversion is applied, **convert each raw value before computing the band, then order the band ascending** (because `90 - x` flips ordering). Confidence-none metrics are emitted with `range: []`.

The mapping is a module constant `MAPPING` (single source of truth). The CSV column for `(our_metric, context)` is `f"{EVENT[context]}-{FEATURE}"`.

**Files:**
- Create: `coach/tests/fixtures/tiny_caddieset.csv`
- Modify: `coach/norms/build_norms.py`
- Test: `coach/tests/test_build_norms.py`

- [ ] **Step 1: Create the tiny synthetic CSV fixture**

Create `coach/tests/fixtures/tiny_caddieset.csv`. It only needs the columns the mapping touches (`0/3/5-SHOULDER-ANGLE` for FACEON, `0/5-SPINE-ANGLE` for DTL) plus `View`. Values are hand-chosen so the bands are predictable; includes clamp artifacts (`0.0`, `180.0`) and an `inf` that cleaning must drop. Each block has 11 usable values so p10/median/p90 land on round numbers.

```csv
View,0-SHOULDER-ANGLE,3-SHOULDER-ANGLE,5-SHOULDER-ANGLE,0-SPINE-ANGLE,5-SPINE-ANGLE
FACEON,10,20,15,,
FACEON,11,21,16,,
FACEON,12,22,17,,
FACEON,13,23,18,,
FACEON,14,24,19,,
FACEON,15,25,20,,
FACEON,16,26,21,,
FACEON,17,27,22,,
FACEON,18,28,23,,
FACEON,19,29,24,,
FACEON,20,30,25,,
FACEON,0.0,180.0,inf,,
DTL,,,,70,75
DTL,,,,71,76
DTL,,,,72,77
DTL,,,,73,78
DTL,,,,74,79
DTL,,,,75,80
DTL,,,,76,81
DTL,,,,77,82
DTL,,,,78,83
DTL,,,,79,84
DTL,,,,80,85
DTL,,,,0.0,180.0
```

For the `0-SHOULDER-ANGLE` block (10..20, after dropping `0.0`): p10≈10.9, median≈15.0, p90≈19.1 (the exact winsorized/interpolated values are asserted in Step 5 with tolerance). For `0-SPINE-ANGLE` (70..80) converted `90-x` → 10..20 reversed; band ascending ≈ [10.9, 15.0, 19.1].

- [ ] **Step 2: Write the failing tests for `MAPPING` and `build_entries`**

Append to `coach/tests/test_build_norms.py`:

```python
import os

FIX = os.path.join(os.path.dirname(__file__), "fixtures", "tiny_caddieset.csv")

MAPPED = {"shoulder_tilt_deg", "spine_angle_deg"}
NONE_METRICS = {
    "hip_tilt_deg", "shoulder_turn_deg", "hip_turn_deg",
    "hip_sway_in", "head_sway_in", "early_extension_in", "hand_depth_in",
}


def test_mapping_covers_all_nine_metrics_exactly():
    metrics = {m for (m, _ctx) in b.MAPPING} | b.NONE_REASONS.keys()
    assert metrics == MAPPED | NONE_METRICS
    assert len(MAPPED | NONE_METRICS) == 9


def test_build_entries_mapped_metrics_have_bands():
    entries = b.build_entries(FIX)
    st = entries["shoulder_tilt_deg"]
    assert st["confidence"] == "medium"
    assert st["units"] == "deg"
    assert "CaddieSet" in st["source"] and "NOT a validated ideal" in st["source"]
    low, high = st["range"]
    assert low < high
    # address block 10..20 -> p10/p90 roughly 10.9 / 19.1
    assert abs(low - 10.9) < 0.6
    assert abs(high - 19.1) < 0.6
    # per-context bands recorded under "contexts"
    assert set(st["contexts"]) == {"address", "top", "impact"}


def test_build_entries_spine_conversion_applied_and_ascending():
    entries = b.build_entries(FIX)
    sp = entries["spine_angle_deg"]
    assert sp["confidence"] == "medium"
    # 0-SPINE-ANGLE 70..80 vs horizontal -> 90-x = 10..20 vs vertical
    low, high = sp["contexts"]["address"]["range"]
    assert low < high                      # ascending after the 90-x flip
    assert abs(low - 10.9) < 0.6
    assert abs(high - 19.1) < 0.6
    # top has NO spine feature in CaddieSet -> not in contexts
    assert "top" not in sp["contexts"]
    assert "impact" in sp["contexts"] and "address" in sp["contexts"]


def test_build_entries_none_metrics_are_history_only():
    entries = b.build_entries(FIX)
    for m in NONE_METRICS:
        e = entries[m]
        assert e["confidence"] == "none"
        assert e["range"] == []
        assert e["reason"]            # documented why
```

- [ ] **Step 3: Run to verify they fail**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute 'MAPPING'`.

- [ ] **Step 4: Implement `MAPPING`, `NONE_REASONS`, top-level constants, and `build_entries`**

Append to `coach/norms/build_norms.py`:

```python
# --- The mapping (single source of truth; see plan doc for rationale) ---------

# Named swing phase -> CaddieSet event index (0=address ... 7=finish).
# ASSUMPTION: standard 8-event sequence; CaddieSet README does not name events.
EVENT = {"address": 0, "top": 3, "impact": 5}

SOURCE_LINE = (
    "CaddieSet (damilab, MIT) - mixed-skill population p10-p90 typical range, "
    "NOT a validated ideal. https://github.com/damilab/CaddieSet"
)

# (our_metric, context) -> (caddieset_feature, view, conversion_kind)
MAPPING = {
    ("shoulder_tilt_deg", "address"): ("SHOULDER-ANGLE", "FACEON", "none"),
    ("shoulder_tilt_deg", "top"):     ("SHOULDER-ANGLE", "FACEON", "none"),
    ("shoulder_tilt_deg", "impact"):  ("SHOULDER-ANGLE", "FACEON", "none"),
    ("spine_angle_deg", "address"):   ("SPINE-ANGLE", "DTL", "vertical_from_horizontal"),
    ("spine_angle_deg", "impact"):    ("SPINE-ANGLE", "DTL", "vertical_from_horizontal"),
    # NOTE: spine top (event 3) intentionally absent — CaddieSet has no 3-SPINE-ANGLE.
}

MAPPED_UNITS = {"shoulder_tilt_deg": "deg", "spine_angle_deg": "deg"}

# Metrics with NO defensible CaddieSet source -> confidence:"none".
NONE_REASONS = {
    "hip_tilt_deg":
        "CaddieSet has no hip-line-angle-vs-horizontal feature; HIP-LINE/"
        "HIP-SHIFTED are displacements and HIP-ROTATION/HIP-ANGLE are rotations.",
    "shoulder_turn_deg":
        "CaddieSet SHOULDER-ANGLE is a tilt vs horizontal, not "
        "rotation-relative-to-address; no shoulder-turn feature exists.",
    "hip_turn_deg":
        "Closest CaddieSet features (HIP-ROTATION/HIP-ANGLE, pelvis rotation "
        "vs address) have severe clamp artifacts (floods of 0.0, spikes of "
        "180.0), an unverifiable zero-point/axis vs our coarse foreshortening "
        "estimate, and are absent at impact (FACEON) — not defensible.",
    "hip_sway_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "head_sway_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "early_extension_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
    "hand_depth_in":
        "CaddieSet positional features are normalized ratios, not inches; "
        "needs calibration + literature.",
}

ALL_METRICS = sorted(MAPPED_UNITS.keys() | NONE_REASONS.keys())


def _load_rows(csv_path):
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _column_values(rows, view, column):
    """Float-parse one column for rows of the given View. Blank -> skipped,
    'inf'/'nan' strings -> kept as float so clean_values drops them."""
    out = []
    for r in rows:
        if r.get("View") != view:
            continue
        raw = r.get(column, "")
        if raw is None or raw == "":
            continue
        try:
            out.append(float(raw))
        except ValueError:
            continue
    return out


def _band_for(rows, our_metric, context):
    feature, view, conv = MAPPING[(our_metric, context)]
    column = f"{EVENT[context]}-{feature}"
    raw = _column_values(rows, view, column)
    cleaned = clean_values(raw)
    if conv != "none":
        cleaned = [convert(v, conv) for v in cleaned]
    pct = percentiles(cleaned)
    if pct is None:
        return None
    p10, med, p90 = pct
    low, high = min(p10, p90), max(p10, p90)   # ascending even after 90-x flip
    return {"range": [low, high], "median": med, "n": len(cleaned)}


def build_entries(csv_path=CSV_PATH):
    """Return {metric_name: entry} for all 9 metrics, schema-compatible with
    coach.norms (each entry has range/units/source/confidence)."""
    rows = _load_rows(csv_path)
    entries = {}

    # Mapped metrics: collect per-context bands; the top-level `range` is the
    # union (min low .. max high) across that metric's contexts so the simple
    # compare() path still works; per-context detail lives under `contexts`.
    mapped_metrics = sorted({m for (m, _c) in MAPPING})
    for m in mapped_metrics:
        contexts = {}
        for (mm, ctx) in MAPPING:
            if mm != m:
                continue
            band = _band_for(rows, m, ctx)
            if band is not None:
                contexts[ctx] = band
        lows = [c["range"][0] for c in contexts.values()]
        highs = [c["range"][1] for c in contexts.values()]
        entries[m] = {
            "range": [min(lows), max(highs)] if contexts else [],
            "units": MAPPED_UNITS[m],
            "source": SOURCE_LINE,
            "confidence": "medium",
            "contexts": contexts,
            "comment": ("Mixed-skill population typical range (p10-p90), NOT a "
                        "validated ideal. Per-phase bands under 'contexts'."),
        }

    for m, reason in NONE_REASONS.items():
        entries[m] = {
            "range": [],
            "units": "in" if m.endswith("_in") else "deg",
            "source": None,
            "confidence": "none",
            "reason": reason,
            "comment": "No defensible CaddieSet source; coach uses player history.",
        }

    return entries
```

- [ ] **Step 5: Run to verify they pass**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: PASS (12 passed).

- [ ] **Step 6: Commit**

```bash
git add coach/norms/build_norms.py coach/tests/test_build_norms.py coach/tests/fixtures/tiny_caddieset.csv
git commit -m "feat(norms): CaddieSet->our-metric mapping + build_entries with conversion"
```

---

## Task 5: `_meta` block + `main()` writer (TDD)

`build_meta()` returns the `_meta` dict (generated-date placeholder, attribution, "population not ideal" disclaimer, list of confidence-none metrics + why, the event→phase assumption). It MUST contain the word "human" or "curated" so `test_norms.py::test_load_norms_has_meta_disclaimer` keeps passing. `main()` writes `{"_meta": ..., **entries}` to `norms.json` deterministically (sorted keys, trailing newline) and returns the path.

**Files:**
- Modify: `coach/norms/build_norms.py`
- Test: `coach/tests/test_build_norms.py`

- [ ] **Step 1: Add failing tests**

Append to `coach/tests/test_build_norms.py`:

```python
def test_meta_has_disclaimer_and_none_list():
    meta = b.build_meta()
    text = (meta["status"] + " " + meta["note"]).lower()
    assert "human" in text or "curated" in text     # keeps test_norms happy
    assert "not" in meta["note"].lower() and "ideal" in meta["note"].lower()
    assert "CaddieSet" in meta["attribution"]
    # every confidence:none metric is listed with a reason
    for m in NONE_METRICS:
        assert m in meta["confidence_none"]


def test_main_writes_deterministically(tmp_path):
    out = tmp_path / "norms.json"
    p1 = b.main(csv_path=FIX, out_path=str(out))
    first = out.read_text(encoding="utf-8")
    p2 = b.main(csv_path=FIX, out_path=str(out))
    second = out.read_text(encoding="utf-8")
    assert p1 == p2 == str(out)
    # deterministic except the generated date line, which we blank for the diff
    import re
    norm = lambda s: re.sub(r'"generated":\s*"[^"]*"', '"generated":"X"', s)
    assert norm(first) == norm(second)
```

- [ ] **Step 2: Run to verify they fail**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: FAIL — `AttributeError: ... has no attribute 'build_meta'`.

- [ ] **Step 3: Implement `build_meta` and `main`**

Append to `coach/norms/build_norms.py`:

```python
import datetime  # noqa: E402  (kept with other imports conceptually; top is fine too)


def build_meta():
    return {
        "status": "Generated from CaddieSet, not human-curated ideals",
        "generated": datetime.date.today().isoformat(),
        "note": (
            "Bands are CaddieSet mixed-skill POPULATION typical ranges "
            "(p10-p90), NOT validated ideal/good-bad thresholds and NOT a "
            "human-curated standard. Treat them as 'where most swings land', "
            "not 'what you should do'. Metrics with confidence 'none' have no "
            "defensible CaddieSet source and the coach falls back to the "
            "player's own history for them."
        ),
        "attribution": (
            "Derived from CaddieSet (damilab, MIT License). "
            "https://github.com/damilab/CaddieSet — see coach/norms/data/SOURCE.md."
        ),
        "event_phase_assumption": (
            "CaddieSet events 0..7 mapped to phases address=0, top=3, impact=5 "
            "(standard 8-event golf sequence; upstream does not name events)."
        ),
        "units_doc": "range is [low, high] inclusive in the stated units; "
                     "empty range means no ideal (history-only).",
        "confidence_none": dict(NONE_REASONS),
    }


def main(csv_path=CSV_PATH, out_path=OUT_PATH):
    entries = build_entries(csv_path)
    doc = {"_meta": build_meta()}
    for k in sorted(entries):
        doc[k] = entries[k]
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=2, sort_keys=True)
        f.write("\n")
    return out_path


if __name__ == "__main__":
    path = main()
    print(f"wrote {path}")
```

- [ ] **Step 4: Run to verify they pass**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: PASS (14 passed).

- [ ] **Step 5: Commit**

```bash
git add coach/norms/build_norms.py coach/tests/test_build_norms.py
git commit -m "feat(norms): _meta block + deterministic main() writer"
```

---

## Task 6: Generated JSON round-trips through `coach.norms` (TDD)

Prove the emitted JSON is consumable: `load_norms` reads it, `compare()` returns in-range / out-of-range for a mapped metric, and history-only for a confidence-none metric. This test generates a `norms.json` from the **tiny fixture** into a temp file and points `load_norms` at it (so it does not depend on the full vendored CSV).

**Files:**
- Test: `coach/tests/test_build_norms.py`

- [ ] **Step 1: Add the failing integration test**

Append to `coach/tests/test_build_norms.py`:

```python
from coach import norms as coach_norms


def test_generated_json_loads_and_compares(tmp_path):
    out = tmp_path / "norms.json"
    b.main(csv_path=FIX, out_path=str(out))
    data = coach_norms.load_norms(str(out))

    assert "_meta" in data
    # mapped metric: in-range value inside [low, high]
    st = data["shoulder_tilt_deg"]
    low, high = st["range"]
    mid = (low + high) / 2.0
    r_in = coach_norms.compare("shoulder_tilt_deg", mid, norms=data)
    assert r_in["in_range"] is True
    assert r_in["use_history_only"] is False

    # mapped metric: out-of-range value above high
    r_out = coach_norms.compare("shoulder_tilt_deg", high + 5.0, norms=data)
    assert r_out["in_range"] is False
    assert r_out["direction"] == "above"

    # confidence:none metric -> history-only path
    r_hist = coach_norms.compare("hip_sway_in", 1.0, norms=data)
    assert r_hist["confidence"] == "none"
    assert r_hist["in_range"] is None
    assert r_hist["use_history_only"] is True
```

- [ ] **Step 2: Run to verify it passes (logic already exists)**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py::test_generated_json_loads_and_compares -q`
Expected: PASS. (If it fails, the generator output is not schema-compatible — fix `build_entries`, not the test.)

- [ ] **Step 3: Run the whole build-norms test file**

Run: `"<PY>" -m pytest coach/tests/test_build_norms.py -q`
Expected: PASS (15 passed).

- [ ] **Step 4: Commit**

```bash
git add coach/tests/test_build_norms.py
git commit -m "test(norms): generated JSON loads + compares via coach.norms"
```

---

## Task 7: Generate the real `norms.json` + full-suite gate (build step)

Now run the generator against the **vendored full CSV** to produce the real `norms.json`, and confirm the existing coach suite still passes with it.

**Files:**
- Modify: `coach/norms/norms.json` (regenerated)
- Possibly modify: `coach/tests/test_norms.py` (only if `_meta` wording breaks it — not expected)

- [ ] **Step 1: Regenerate `norms.json` from the vendored CSV**

Run: `"<PY>" -m coach.norms.build_norms`
Expected: prints `wrote .../coach/norms/norms.json`.

- [ ] **Step 2: Eyeball the generated file**

Run: `"<PY>" -c "import json; d=json.load(open('coach/norms/norms.json')); print('meta?', '_meta' in d); print('shoulder_tilt_deg', d['shoulder_tilt_deg']['range'], d['shoulder_tilt_deg']['confidence']); print('spine_angle_deg', d['spine_angle_deg']['range'], 'top?', 'top' in d['spine_angle_deg']['contexts']); print('hip_turn_deg', d['hip_turn_deg']['confidence'], d['hip_turn_deg']['range'])"`
Expected (approx, from the real data):
- `meta? True`
- `shoulder_tilt_deg` range roughly `[5.x, 33.x]` (union of address ~[5.5,16.8], top ~[8.8,26.6], impact ~[13.1,32.8]), confidence `medium`.
- `spine_angle_deg` range roughly `[2.x, 31.x]` (converted), `top? False`.
- `hip_turn_deg` confidence `none`, range `[]`.

- [ ] **Step 3: Run determinism check (regenerate, expect no diff except date)**

Run: `"<PY>" -m coach.norms.build_norms && git diff --stat coach/norms/norms.json`
Expected: no changes, or only the `generated` date line if the date changed. (Two runs on the same day produce byte-identical output.)

- [ ] **Step 4: Run the coach + store suites (the gate)**

Run: `"<PY>" -m pytest coach/ store/ -q`
Expected: all PASS. In particular `coach/tests/test_norms.py::test_load_norms_has_meta_disclaimer` passes because the new `_meta["status"]` contains "human-curated" / `_meta["note"]` contains "human". If that one test fails on wording, update its assertion to match the new `_meta` (the disclaimer is genuinely present) — do NOT weaken the disclaimer.

- [ ] **Step 5: Commit the generated norms.json**

```bash
git add coach/norms/norms.json
git commit -m "feat(norms): real CaddieSet-derived bands (shoulder_tilt, spine_angle); rest confidence:none"
```

---

## Task 8: Final verification gate

- [ ] **Step 1: Full target suite green**

Run: `"<PY>" -m pytest coach/ store/ -q`
Expected: PASS (existing tests + 15 new build-norms tests).

- [ ] **Step 2: Generator is reproducible from scratch**

Run: `"<PY>" -m coach.norms.build_norms` then `git status --porcelain coach/norms/norms.json`
Expected: clean (no diff) on a same-day rerun — confirms the build step is deterministic.

- [ ] **Step 3: Confirm honesty invariants in the real file**

Run: `"<PY>" -c "import json; d=json.load(open('coach/norms/norms.json')); none=[k for k,v in d.items() if k!='_meta' and v['confidence']=='none']; band=[k for k,v in d.items() if k!='_meta' and v['confidence']!='none']; print('real bands:', sorted(band)); print('confidence none:', sorted(none)); assert sorted(band)==['shoulder_tilt_deg','spine_angle_deg'] or sorted(band)==['shoulder_tilt_deg','spine_angle_deg'][::-1]; assert len(none)==7; print('OK: 2 bands, 7 none')"`
Expected: `real bands: ['shoulder_tilt_deg', 'spine_angle_deg']` (order may differ), `confidence none:` lists the 7 metrics, `OK: 2 bands, 7 none`.

---

## Self-Review

**Spec coverage:**
- Vendor CSV + SOURCE.md attribution → Task 1. ✓
- Generator that cleans (inf/NaN/clamp/winsorize), percentiles, conversions, writes schema-correct JSON with `_meta` → Tasks 2–5. ✓
- Inch metrics → confidence none with the exact "normalized ratios, not inches" reason → Task 4 `NONE_REASONS`. ✓
- Degree metrics mapped only where axis/units align, with documented conversion (`90-x` for spine) and confidence ≤ medium → Task 4 `MAPPING` + Task 3 `convert`. ✓
- "Mixed-skill population, not ideal" in every derived `source` + `_meta` → Tasks 4–5. ✓
- TDD on cleaning, percentile+conversion math (tiny synthetic CSV), and JSON round-trip through `load_norms`/`compare` incl. history-only path → Tasks 2,3,4,6. ✓
- Full norms.json produced by running the generator (build step) → Task 7. ✓
- Gates: `pytest coach/ store/ -q` green; deterministic regen; suite passes with real norms.json → Tasks 7–8. ✓

**Placeholder scan:** No "TBD/handle edge cases/similar to" placeholders; all code shown in full. ✓

**Type/name consistency:** `clean_values`, `percentiles`, `convert`, `MAPPING`, `NONE_REASONS`, `EVENT`, `build_entries`, `build_meta`, `main`, `SOURCE_LINE`, `<PY>` used identically across tasks. `build_entries` returns per-metric entries with `range/units/source/confidence/contexts/reason` consistently; tests reference exactly those keys. ✓

**Risk note:** The event→phase index assumption (address=0/top=3/impact=5) is the main interpretive risk — it is documented in `_meta.event_phase_assumption` and the SOURCE/plan, and only affects which CaddieSet column is read (a wrong guess shifts the band, it does not corrupt the schema). `hip_turn_deg` is deliberately `none` despite a tempting HIP-ROTATION/HIP-ANGLE feature; this is the conservative/honest call given clamp artifacts and axis uncertainty.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-norms-caddieset.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**
