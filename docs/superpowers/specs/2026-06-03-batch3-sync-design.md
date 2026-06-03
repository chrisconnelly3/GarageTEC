# Batch 3 — Sync (Swing ↔ Shot Correlation)

**Project:** GarageTEC
**Status:** Approved design (2026-06-03)
**Type:** Batch 3 rock. Depends on Batch 0 (store), Batch 1 (swings + shots exist).

---

## 1. Purpose

Pair each camera **swing** with its R50 **shot** so body motion connects to ball
result. Matching is automatic (time + order hybrid) with manual correction
available, and is constrained to the **same player + session**, which our
multi-user tagging makes both safe and easy.

## 2. Key simplification — match within (player, session)

Every swing and every shot already carries `player_id` + `session_id`. Sync only
ever considers candidates that share both. This:
- prevents cross-player mismatches automatically (brother's shot can't grab your
  swing), and
- shrinks each matching problem to one person's shots/swings in one session,
  where order + time are highly reliable.

## 3. Matching strategy (hybrid)

Within a (player, session):
- **Primary — time:** pair a swing to the shot whose `captured_at` is closest to
  the swing's **impact wall-clock time**, within a window (default ±a few
  seconds, configurable). Swing impact wall-clock = video/recording start time +
  the impact moment's `time_s` (live capture supplies it directly).
- **Tiebreak / fallback — order:** the k-th unmatched swing pairs with the k-th
  unmatched shot when timestamps are unavailable, clocks drift, or two
  candidates tie.
- **Confidence** per proposed pair from time delta + order agreement.
- **Unmatched is normal:** a swing with no shot (practice swing, mishit the R50
  missed) and a shot with no swing (cameras missed) are left unlinked, not forced.

## 4. Auto + manual fix

- `auto_reconcile` applies links above a confidence threshold via
  `store.repo.link_shot_to_swing`; ambiguous/low-confidence pairs are **not**
  auto-applied.
- `propose_matches` returns candidate pairs + confidence **without applying** —
  the Screen rock uses this to show suggestions and let the user confirm.
- `apply_match(swing_id, shot_id)` / `unlink(swing_id)` let the UI correct any
  pairing.

## 5. Triggering (immediacy)

- **Incremental:** when a new swing is stored or a new shot arrives, attempt to
  match it against the unmatched counterparts in its (player, session) — so a
  live swing links to its shot within moments.
- **Batch:** `reconcile_session(session_id)` re-runs matching for a whole
  session (for offline/recorded reconciliation or cleanup).

## 6. Architecture (`sync/` package)

| Module | Responsibility |
|---|---|
| `sync/matcher.py` | Pure logic: given unmatched swings (with impact times/order) + unmatched shots (with capture times/order), return ranked `MatchProposal(swing_id, shot_id, confidence, reason)`. No DB. |
| `sync/service.py` | Loads unmatched candidates for a (player, session) via store, runs `matcher`, applies confident links, returns the rest as proposals. Exposes `auto_reconcile`, `propose_matches`, `apply_match`, `unlink`, `on_new_swing`, `on_new_shot`. |
| `sync/run.py` | CLI: `python -m sync.run --session <id>` (reconcile) / `--all`. |

## 7. Data flow

```
store: list_unmatched_swings(session, player) + list_unmatched_shots(session, player)
        │  (swings carry impact time via moments; shots carry captured_at)
        ▼
matcher.propose(swings, shots) -> [MatchProposal(confidence)]
        │
        ├─ confidence >= threshold ─► link_shot_to_swing(shot, swing)   (auto)
        └─ else ─────────────────────► return as proposals for UI confirm
```

## 8. Store additions needed (Batch 0)

Small additions to the store contract (added to the Batch 0 spec; folded into the
Batch 0 plan when it is built):
- `list_unmatched_swings(session_id=None, player_id=None) -> list[Swing]` (shot_id IS NULL)
- `list_unmatched_shots(session_id=None, player_id=None) -> list[Shot]` (swing_id IS NULL)
- `unlink_shot(swing_id) -> None` (clear both sides of the link)

Swing impact time: `get_moments(swing_id)` already provides the `impact` frame's
`time_s`; the swing's recording start time comes from the swing row / source
video metadata (Batch 1 records it; if absent, Sync uses order-only).

## 9. Testing

- **matcher:** synthetic candidates — equal counts with clean times → correct
  1:1 pairs; an extra swing (practice) → it stays unmatched, the rest pair;
  an extra shot → unmatched; clustered times → order breaks the tie; assert
  confidence ordering.
- **multi-user safety:** swings/shots from two players overlapping in time →
  no cross-player link (scoped by player+session).
- **service:** in-memory store with one player/session, 3 swings + 3 shots →
  `auto_reconcile` links the confident ones; `propose_matches` returns the rest;
  `apply_match` + `unlink` mutate links correctly.
- **incremental:** `on_new_shot` links it to the waiting unmatched swing.

## 10. Risks

- Clock alignment camera↔R50 in live mode → window tolerance + order fallback;
  expose the window as config.
- Recorded-offline swings often have no same-session shot → simply unmatched
  (expected); no false links forced.
- Rapid-fire shots within the time window → order tiebreak + manual fix.
- Threshold tuning → conservative auto-link threshold; everything else goes to
  the UI rather than risking a wrong auto-link.

## 11. Consumes / Produces

- **Consumes (Batch 0):** `list_unmatched_swings`, `list_unmatched_shots`,
  `get_moments`, `link_shot_to_swing`, `unlink_shot`.
- **Produces:** `swing.shot_id` / `shot.swing_id` links (the join that lets AI
  coach + Screen show body + ball together).
