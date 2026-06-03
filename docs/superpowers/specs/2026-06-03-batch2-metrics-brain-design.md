# Batch 2 — Metrics Brain

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 2 rock. Depends on Batch 0 (store) + Batch 1 (camera/pose/chop stored pose + moments).

---

## 1. Purpose

Turn stored body data into golf numbers. For a given swing, read its pose
timelines (both views) + phase moments, compute the metric set, and write
`metric` rows. Pluggable registry so new metrics are cheap to add; idempotent so
re-running backfills history as the registry grows.

## 2. Scope

**In scope (v1 metric set)**

Reliable in 2D (exact-ish):
- **shoulder tilt** (face-on) — shoulder-line angle vs horizontal. [deg]
- **hip tilt** (face-on) — hip-line angle vs horizontal. [deg]
- **head sway** (face-on) — lateral head-center displacement from address. [in]
- **hip sway / pelvis shift** (face-on) — lateral hip-center displacement. [in]
- **spine angle** (down-line) — torso (hip→shoulder) lean from vertical. [deg]
- **early extension** (down-line) — hips moving toward the ball / standing up:
  forward+vertical hip-center shift from address through impact. [in]
- **hand depth** (down-line) — hand horizontal distance from a body reference
  (trail shoulder) at top/impact. [in]

Rough 2D estimates (clearly flagged low-confidence; upgrade with 3D later):
- **shoulder turn** (face-on) — estimated from shoulder-width foreshortening vs
  address. [deg, low-confidence]
- **hip turn** (face-on) — estimated from hip-width foreshortening. [deg, low-conf]

**Out of scope**
- **Kinematic sequence / sequencing** — deferred to a later pass.
- True 3D rotations (need the 3D-pose upgrade).
- Pose/segmentation (Batch 1) and storage schema (Batch 0).

## 3. Units & calibration

- Angles → **degrees**, exact, no calibration.
- Linear metrics → **inches**, via the per-player shoulder-ratio ruler from
  Slice 1: `ppi = shoulder_px(address) / (0.24 × player.height_in)`. Player
  height read from the swing's player profile. Also store raw **pixels** as a
  backup context where useful. Method string records the calibration used.
- Inch values are estimates (~±0.3–0.5 in); true calibration is a later upgrade.

## 4. Confidence flagging

The `metric.method` field carries the computation method **and** a confidence
tag, e.g. `method="foreshortening_2d;confidence=low"` for rotation estimates and
`method="exact"` / `method="shoulder_ratio_0.24"` for reliable ones. The Screen
and AI-coach rocks read this tag to caveat low-confidence numbers. (No schema
change to Batch 0 — confidence lives in `method`.)

## 5. Architecture (`metrics/` package)

| Module | Responsibility |
|---|---|
| `metrics/geometry.py` | Shared math: line angle vs horizontal/vertical, lateral/forward displacement, foreshortening→rotation estimate, `ppi_from_height`. Pure functions over landmark coords. |
| `metrics/registry.py` | The metric registry: each entry = `MetricDef(name, view, contexts, fn)` where `fn(ctx) -> list[Metric]`. New metrics register here. |
| `metrics/defs/*.py` | The metric functions: `tilt.py` (shoulder/hip tilt), `sway.py` (head/hip sway), `spine.py`, `extension.py`, `hand_depth.py`, `rotation.py` (rough turns). Each imports geometry. |
| `metrics/compute.py` | Orchestrator: load `pose_frame`s (both views) + `moment`s + player via `store.repo`; build a `MetricContext`; run every registered metric; **replace** this swing's metric rows; return the list. |
| `metrics/run.py` | CLI: `python -m metrics.run --swing <id>` or `--all-missing` (compute for swings lacking metrics). |

`MetricContext` (passed to each metric fn): `{pose_face_on, pose_down_line,
moments_by_kind, ppi, player, fps}` — pose timelines smoothed, moments indexed by
kind for easy lookup of address/top/impact frames.

## 6. Data flow

```
store: get_pose_frames(swing,"face_on"/"down_line"), get_moments(swing),
       get_swing -> player.height_in
        │
        ▼
build MetricContext (smooth pose, compute ppi from address shoulder width)
        │
        ▼
for each MetricDef in registry: fn(ctx) -> [Metric(name, context, value, unit, method)]
        │
        ▼
store.repo: delete existing metrics for swing, then save_metrics(all)   # idempotent
```

## 7. Per-metric contexts (where each is reported)

- shoulder tilt, hip tilt, spine angle: at **address, top, impact**.
- head sway, hip sway: at **top, impact, max** (address = 0 reference).
- early extension: at **impact** (vs address) and **max**.
- hand depth: at **top, impact**.
- shoulder turn, hip turn (rough): at **top, impact**.

## 8. Idempotency & growth

- Recompute **replaces** a swing's metrics (delete-by-swing then insert), so
  adding a new `MetricDef` + re-running `--all` backfills the new metric across
  history without duplicating existing ones.
- Each metric value records its `method` (incl. calibration + confidence), so
  changes in method are auditable over time.

## 9. Testing

- **geometry:** unit tests with known coordinates → exact angle, displacement,
  `ppi`, and foreshortening-rotation estimate (e.g. shoulders at full width →
  ~0° turn; half width → expected arccos angle).
- **each metric fn:** synthetic `MetricContext` with hand-built pose at
  address/top/impact → assert expected value + correct `method`/confidence tag.
- **compute orchestrator:** seed an in-memory store with a synthetic swing
  (pose both views + moments + player height) → run → assert expected metric
  rows; re-run → assert replaced (no duplicates).
- **rotation flagging:** assert rough metrics carry `confidence=low` in `method`.

## 10. Risks

- 2D rotation estimates are coarse (foreshortening is noisy at small angles) →
  flagged low-confidence; documented as estimates; superseded by 3D later.
- Pose jitter propagates into metrics → smoothing in `MetricContext`; metrics
  read at phase frames (stable points) where possible, or small windows around
  them.
- Inch accuracy bounded by the height-ratio calibration → method recorded;
  honest in UI.
- Depends on Batch 1 having stored correct moments; a wrong `impact` frame skews
  values → metrics tolerate missing/low-confidence moments (skip + flag).

## 11. Consumes / Produces

- **Consumes (Batch 0):** `get_pose_frames`, `get_moments`, `get_swing`,
  player height, `save_metrics` (+ a delete-by-swing helper or `save_metrics`
  with replace semantics — add `clear_metrics(swing_id)` to the store).
- **Produces:** `metric` rows per swing, consumed by AI coach + Screen.

> Note: this rock needs a `clear_metrics(swing_id)` repo function for idempotent
> recompute — a small addition to the Batch 0 store API at build time.
