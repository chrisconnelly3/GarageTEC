# Batch 4 — AI Coach

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 4 rock (parallel with Screen). Depends on Batch 0/1/2/3 (metrics + shots + links).

---

## 1. Purpose

Turn a swing's numbers + ball result into specific, evidence-tied coaching: a
short post-swing read, plus session summaries and trend notes. Grounded in the
swing's own metrics, the matched shot, the player's history, and reputable ideal
ranges — never generic.

## 2. LLM backend (pluggable; cloud default)

- `LLMBackend` interface: `complete(system, user, schema) -> dict`.
- `CloudClaude` (default) — Anthropic API; fastest + best on normal mini-PC
  hardware (tiny payloads, ~1–2s).
- `LocalOllama` (optional) — for offline/privacy/no-cost once a capable GPU is
  present (see spec note on min specs). Same interface, swap via config.
- Backend chosen by config/env; the rest of the rock is backend-agnostic.

## 3. Anti-generic grounding (the core idea)

The LLM never free-associates. We build a **structured context** of real numbers
and ask for **structured, cited output**:

Context assembled from the store for a swing:
- the swing's `metric`s (name, context, value, unit, method/confidence);
- the matched `shot` (ball/club data) if linked;
- the player's **baseline + recent trend** per metric (via `swing_history`);
- **ideal ranges** per metric from the norms dataset (value, source, confidence);
- player profile (height, handedness) + club.

Output schema (LLM must return JSON):
```json
{
  "headline": "one-line plain summary",
  "findings": [
    {"metric": "hip_sway_in", "context": "impact", "value": 2.5, "unit": "in",
     "vs_baseline": "+1.1 in more than your norm", "vs_ideal": "above the 0-1.5 in ideal",
     "ball_effect": "matches the pull you saw", "severity": "high"}
  ],
  "drills": [{"name": "...", "why": "...", "how": "..."}],
  "confidence_notes": ["hip turn is a rough 2D estimate"]
}
```
Every finding must cite a real metric + value and compare to baseline and/or
ideal. Low-confidence metrics (e.g. rough 2D rotations) are surfaced as such.

## 4. Comparison sources

- **Own history (primary):** per-metric baseline = robust central value of the
  player's recent swings (e.g. median of last N), plus trend direction, via
  `store.repo.swing_history`.
- **Reputable ideals (permanent):** `coach/norms/norms.json` — per metric (and
  per club where data exists): `{range, units, source, confidence}`. Sourced from
  credible golf-biomechanics references; **citations required**; metrics lacking
  reputable data are marked `confidence: "none"` and the coach falls back to
  history-only for them. This file is curated data, not invented.

## 5. Outputs & storage

- **Per-swing read:** generated after metrics + sync for a swing; saved.
- **Session summary:** on session end, summarize the session's swings + trends.
- **Stored** via a new `coaching` table (Batch 0 addition):
  `coaching(id, swing_id|null, session_id|null, kind, content_json, model,
  created_at)`; repo `save_coaching` / `get_coaching`.
- The Screen rock renders coaching; this rock only generates + stores it.

## 6. Architecture (`coach/` package)

| Module | Responsibility |
|---|---|
| `coach/context.py` | Build the structured context dict for a swing/session from the store (metrics, shot, history/baseline, profile). |
| `coach/norms.py` | Load `norms.json`; compare a metric value to its ideal range → `{in_range, delta, source, confidence}`. |
| `coach/backend.py` | `LLMBackend` interface + `CloudClaude`, `LocalOllama`, and a `FakeBackend` for tests. |
| `coach/prompt.py` | System/user prompt templates + the output JSON schema + validation. |
| `coach/coach.py` | Orchestrate: build context → backend.complete(schema) → validate → `save_coaching`. `coach_swing(swing_id)`, `coach_session(session_id)`. |
| `coach/run.py` | CLI: `python -m coach.run --swing <id>` / `--session <id>`. |

## 7. Data flow

```
store: metrics + shot + swing_history + profile  ──► context.py ──┐
norms.json ──► norms.py (per-metric ideal compare) ───────────────┤
                                                                   ▼
                                              prompt.py (system+user+schema)
                                                                   ▼
                                              backend.complete(...) -> JSON
                                                                   ▼
                                              validate -> save_coaching(store)
```

## 8. Immediacy

Cloud backend returns a short structured read in ~1–2s after a swing's metrics
land, meeting the post-swing feedback goal. Generation is per-swing and
non-blocking to capture (runs after metrics/sync, async from the catcher).

## 9. Testing (no real API calls)

- **context:** in-memory store with a seeded swing (metrics + linked shot +
  prior swings) → assert the context dict contains the metrics, baseline, trend,
  shot, and ideal comparisons.
- **norms:** value inside/outside an ideal range → correct `in_range`/`delta`;
  metric with `confidence:"none"` → flagged, history-only path.
- **coach orchestrator with `FakeBackend`:** returns canned valid JSON →
  `coach_swing` validates + persists a `coaching` row; bad JSON → retried/raised,
  not persisted.
- **prompt/schema:** output schema validation accepts the canonical example,
  rejects malformed (missing cited metric).
- Real backends covered by a thin smoke test gated behind an env flag (skipped
  in CI).

## 10. Risks

- **Generic/hallucinated feedback** → mitigated by feeding only real numbers,
  forcing cited structured output, and validating the schema; the model can't
  invent metrics that aren't in context.
- **Norms data quality/availability** → citations + confidence flags + history
  fallback; never present a fabricated "ideal".
- **Cost/latency (cloud)** → tiny payloads; per-swing only; cache identical
  contexts; backend swappable to local.
- **Privacy** → local backend option for users who want no data leaving the box.

## 11. Consumes / Produces

- **Consumes (Batch 0–3):** `get_metrics`, `get_swing` (+ linked `shot`),
  `swing_history`, player profile; norms dataset.
- **Produces:** `coaching` rows (per swing + per session), consumed by Screen.
- **Store addition:** `coaching` table + `save_coaching`/`get_coaching` (added to
  Batch 0 spec; folded into the Batch 0 plan at build).
