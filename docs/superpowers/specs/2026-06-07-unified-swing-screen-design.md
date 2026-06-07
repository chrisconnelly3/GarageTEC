# Unified "Swing" screen — merge Live + Review

**Date:** 2026-06-07
**Status:** Approved design, ready for implementation plan
**Area:** `web/frontend` (+ small `web/backend` none expected); touch-first golf-bay UI

## Problem

The **Live** and **Review** screens are ~90% redundant — both render the same
children (swing video player, position stepper / phase timeline, body-mechanic
metric cards, ball/club cards, AI coach read). The only real difference is
*which* swing is shown: Live = the latest as you hit; Review = a chosen past
one. Maintaining two screens duplicates work and splits a single user task
("look at my swing") across two destinations.

## Goal

Collapse Live + Review into **one screen ("Swing")** with two states —
**Following** (newest swing auto-shown) and **Pinned** (studying a chosen past
swing) — and relocate R50 connection status so the header is decluttered without
losing visibility of system state.

## Non-goals

- **Video retention / pruning policy** (disk-space management) — its own future
  spec. This work only adds *graceful handling of already-absent video* on the
  Swing screen (see §6). Metrics/coach/pose data are tiny and kept regardless;
  video is the only large artifact and will be managed separately.
- Any change to how swings are captured, analyzed, or to the metric/coach
  pipelines.

## Approach (chosen)

Evolve `LiveScreen` into **`SwingScreen`**, fold in `ReviewScreen`'s
swing-picker and `getSwing(id)` logic, and **delete `ReviewScreen`**. One
component, two states driven by a single `selectedSwingId`. All existing child
components (`SwingReplay`, `MetricCard`, `LiveTimeline`, `AIInsightCard`) are
reused unchanged except `SwingReplay` gains a "video unavailable" state.

Rejected alternatives: a brand-new component with Live/Review kept as wrappers
(churn, no benefit); two routes under a shared parent (defeats the merge). Both
screens already share every child component, so evolving one in place is
cleanest.

## 1. State model & data flow

`SwingScreen` owns one new piece of state:

```
selectedSwingId: number | null   // null = Following (latest); id = Pinned
```

Derived: `following = selectedSwingId === null`.

Data sources:
- **Swing list** (dropdown + arrows): `getSwings(playerId, sessionId, 50)`.
- **Following:** `getLatestSwing(playerId, sessionId)`; re-fetched on each
  `lastSwing` SSE event (existing `useEvents` signal).
- **Pinned:** `getSwing(selectedSwingId)` (logic absorbed from `ReviewScreen`),
  including the pinned swing's per-club ball history (as Review does today).
- **`newCount`**: number of swings that have arrived since pinning. Baseline =
  newest swing id at the moment of pinning; each `lastSwing` event while pinned
  increments it. Used for the LIVE-pill badge. Reset to 0 when returning to
  Following.

The body layout is unchanged from the current two-column LiveScreen (left:
video → position stepper → coach; right: Ball & Club + Body Mechanics cards).

## 2. Live / Pinned behavior (auto-advance rules)

- **Following (default):** newest swing shows automatically. A new shot
  re-fetches latest and briefly highlights the changed cards (peak moment).
- **Pin:** selecting a swing via the dropdown, the `‹ ›` arrows, or a deep-link
  sets `selectedSwingId` → auto-follow stops.
- **New shot while pinned:** does **NOT** switch the view (no focus-steal);
  `newCount++` and the LIVE pill shows the count badge.
- **Go Live:** tapping the LIVE pill sets `selectedSwingId = null` → jumps to
  newest, `newCount = 0`.
- **Arrows:** `‹` / `›` step through the swing list by index (newest → oldest),
  pinning the stepped-to swing. Stepping `›` past the newest returns to
  Following. `‹` is disabled at the oldest; `›` from any pinned swing moves
  toward newer.

## 3. Control bar (atop the left/swing column)

A slim bar directly above the video: `[ ● LIVE ] [ ‹ ] [ swing dropdown ] [ › ]`.
All targets ≥44px (touch, club-in-hand).

LIVE pill — single control that conveys state AND acts as "Go Live":
| State | Appearance |
|---|---|
| Following, R50 connected | filled green `● LIVE` |
| Following, connected, no shot yet | filled amber `● LIVE` |
| Pinned | outline green `● LIVE`; shows `newCount` badge when > 0; tap → Go Live |
| R50 down | grey/dead `● LIVE` |

Dropdown value is the only "pinned" signal needed:
- Following → `Latest · 7i · 2:14`
- Pinned → `#38 · Driver · 1:58`
List entries: `#<id> · <club> · <time>` (+ ` · R50` if a shot is matched, and
`(latest)` on the newest), reusing Review's current picker formatting.

## 4. R50 status relocation

Remove the verbose header R50 pill. Status survives in three honest places:

1. **Dot on the Start/End Session button** (header):
   green = connected · amber = connected, no shot yet · grey = paused ·
   red = disconnected/error. Maps from `capture.status.status`.
2. **Loud inline state in the video area** (the can't-miss one, shown exactly
   when shots aren't landing):
   - connected, no swings yet → "Waiting for your R50…"
   - disconnected → "⚠ R50 not connected — shots won't record · Reconnect"
     (Reconnect → Connect screen).
3. **Red badge on the gear/Connect sidebar icon** when R50 is in
   error/disconnected; cleared when healthy (the in-screen dot already signals
   the healthy state, so no persistent badge clutter).

Full R50 details + reconnect remain on the **Connect** screen (the bottom gear
icon already routes there — Connect *is* the settings/connection screen).

## 5. Navigation & deep-link

- **Sidebar:** rename item `live` → id `swing`, label **"Swing"**; **remove**
  the `review` item. Other items (History, Sessions, Players, Sync, gear→Connect)
  unchanged. The Sidebar gains an R50-status prop to render the gear badge.
- **App:** `activeTab` default `'swing'`; remove the `ReviewScreen` import/route;
  pass R50 status to `Topbar` (session-button dot) and `Sidebar` (gear badge).
- **Deep-link:** `App` exposes `openSwing(id: number)` that sets a
  pending-pinned id and switches `activeTab` to `'swing'`. `SwingScreen` consumes
  the pending id to set `selectedSwingId` on mount/update. `HistoryScreen` and
  `SessionsScreen` receive an `onOpenSwing(id)` prop wired to their swing rows;
  tapping a swing opens it pinned in Swing.

## 6. Edge & empty states

- **No player selected:** existing "pick a player" prompt.
- **Following, no swings yet, R50 connected:** "Waiting for your R50…".
- **Following, R50 disconnected:** inline disconnected message + Reconnect.
- **Pinned swing, video pruned/absent:** show metrics + coach normally and a
  quiet "video not kept for this swing" placeholder in the `SwingReplay` area
  (distinct from the "no swing video yet" placeholder). This is the one new
  requirement carried in from the storage concern.
- **Pinned swing id missing/deleted:** fall back to Following (latest).
- **Player or session changes while pinned:** reset `selectedSwingId` to `null`
  (Following) — the pinned swing belonged to the previous context.

## 7. Components & files

- **Rename** `web/frontend/src/pages/LiveScreen.tsx` → `SwingScreen.tsx`
  (component `SwingScreen`). Add the control bar, `selectedSwingId`/`newCount`
  state, and Following/Pinned data loading (merging Review's `getSwing` +
  ball-history paths).
- **Delete** `web/frontend/src/pages/ReviewScreen.tsx`. Migrate any still-needed
  formatting (swing-picker labels) into `SwingScreen`.
- **`SwingReplay.tsx`:** add a "video unavailable (pruned)" state — when a swing
  is selected but has no `annotated_video` media, render the placeholder instead
  of an empty player.
- **`App.tsx`:** `activeTab` rename (`live`→`swing`), remove `review` route,
  add `openSwing` plumbing and pending-pin state, pass R50 status to Topbar &
  Sidebar.
- **`Topbar.tsx`:** remove the R50 status pill; add a status dot to the
  Start/End Session button.
- **`Sidebar.tsx`:** rename `live`→`swing` (label "Swing"), remove `review`,
  render a red badge on the gear (Connect) icon from an R50-status prop.
- **`HistoryScreen.tsx` / `SessionsScreen.tsx`:** accept `onOpenSwing(id)` and
  wire it to swing rows.
- **`ConnectScreen.tsx`:** confirm it surfaces full R50 status + reconnect (it is
  the existing connection screen; extend copy only if needed).

## 8. Testing strategy

Frontend (Vitest + Testing Library), in the new `SwingScreen.test.tsx`:
- Following shows the latest swing; a new `lastSwing` event updates it.
- Selecting a swing pins it (loads `getSwing`, auto-follow stops).
- New shot while pinned does NOT switch the view and increments the LIVE badge.
- Tapping LIVE returns to latest and clears the badge.
- `‹ / ›` step through swings; `›` past newest returns to Following.
- Pinned swing with no `annotated_video` → shows the "video not kept" placeholder.
- Changing player/session while pinned resets to Following.
- R50 status drives the Session-button dot and the inline waiting/disconnected
  state; gear badge appears on error.
- Deep-link: `App.openSwing(id)` switches to Swing and pins the id.
- Remove `ReviewScreen.test.tsx`; update any nav test for `swing`/no `review`.

## Acceptance criteria

- One sidebar item ("Swing"); no "Review"; History/Sessions rows open a swing
  pinned in Swing.
- Default state follows the latest shot; selecting/scrubbing pins without
  focus-steal; a single LIVE control returns to live and shows the new-shot
  count; End Session stays in the header in all states.
- No R50 pill in the header; status is visible via the Session-button dot, an
  inline waiting/disconnected message, and a gear badge on error.
- A pinned swing without video shows metrics/coach + a clear placeholder.
- All frontend tests pass; build clean.
