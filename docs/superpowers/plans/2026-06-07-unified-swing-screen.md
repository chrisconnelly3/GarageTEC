# Unified "Swing" Screen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge the Live and Review screens into one "Swing" screen with a Following (auto-latest) / Pinned (study a past swing) state model, relocating R50 status out of the header.

**Architecture:** Evolve `LiveScreen` → `SwingScreen` (keep its two-column body verbatim), add a single `selectedSwingId` state (`null` = Following → `getLatestSwing`; an id = Pinned → `getSwing`). A new `SwingControlBar` renders the LIVE/Go-Live pill + `‹ ›` + dropdown. Delete `ReviewScreen`. App rename `live`→`swing`, remove `review`, add `openSwing(id)` deep-link. R50 status moves to a dot on the Session button, an inline state in the swing area, and a badge on the gear/Connect sidebar icon.

**Tech Stack:** React 18 + TypeScript, Vite, Vitest + @testing-library/react. All work in `web/frontend/`. No backend changes.

**Spec:** `docs/superpowers/specs/2026-06-07-unified-swing-screen-design.md`

**Conventions:** run commands from `web/frontend/`. Test a single file with `npx vitest run <path>`. Brand green `#79BC30`; amber `#E8B931`; red `garage-red`. Existing tests live next to components as `*.test.tsx`.

---

## File map

- **Create** `src/components/SwingControlBar.tsx` — LIVE/Go-Live pill + arrows + dropdown (presentational; all logic via props).
- **Create** `src/components/SwingControlBar.test.tsx`.
- **Create** `src/pages/SwingScreen.tsx` — evolved from `LiveScreen.tsx` (Following/Pinned + control bar + inline R50 states).
- **Create** `src/pages/SwingScreen.test.tsx` — adapted/expanded from `LiveScreen.test.tsx`.
- **Modify** `src/components/SwingReplay.tsx` — add `placeholder` prop (the "video not kept" message).
- **Modify** `src/components/Topbar.tsx` — remove R50 pill; add status dot on the Session button; widen `r50Status` union to include `'error'`.
- **Modify** `src/components/Sidebar.tsx` — rename `live`→`swing`, remove `review`, add an `r50Error` badge on the gear icon.
- **Modify** `src/App.tsx` — route `swing` → `SwingScreen`, remove `review`/`ReviewScreen`, add `openSwing` + `pinnedSwingId`, compute 4-state `r50`, pass deep-link to Sessions/History.
- **Modify** `src/pages/SessionsScreen.tsx` — `onOpenSwing(id)` prop; "View Swings" opens the session's latest swing.
- **Modify** `src/pages/HistoryScreen.tsx` — `onOpenSwing(id)` prop; clicking a hero-chart point opens that swing.
- **Delete** `src/pages/ReviewScreen.tsx` and `src/pages/ReviewScreen.test.tsx`.
- **Delete** `src/pages/LiveScreen.tsx` and `src/pages/LiveScreen.test.tsx` (replaced by SwingScreen).

---

## Task 1: `SwingControlBar` component

A presentational control bar. No data logic — the parent computes everything and passes handlers.

**Files:**
- Create: `web/frontend/src/components/SwingControlBar.tsx`
- Test: `web/frontend/src/components/SwingControlBar.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// web/frontend/src/components/SwingControlBar.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SwingControlBar } from "./SwingControlBar";

const base = {
  following: true,
  newCount: 0,
  r50: "connected" as const,
  label: "Latest · 7i · 2:14",
  swings: [
    { id: 42, created_at: "2024-01-01T10:02:00Z", club: "7 Iron", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
    { id: 41, created_at: "2024-01-01T10:01:00Z", club: "Driver", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  ],
  currentSwingId: 42,
  canPrev: true,
  canNext: false,
  onGoLive: vi.fn(),
  onPrev: vi.fn(),
  onNext: vi.fn(),
  onPickSwing: vi.fn(),
};

describe("SwingControlBar", () => {
  it("shows a solid LIVE pill when following + connected", () => {
    render(<SwingControlBar {...base} />);
    const pill = screen.getByTestId("live-pill");
    expect(pill.className).toContain("bg-garage-green");
    expect(pill.textContent).toMatch(/LIVE/);
  });

  it("shows an outline pill with the new-shot count when pinned", () => {
    render(<SwingControlBar {...base} following={false} newCount={2} currentSwingId={41} canNext />);
    const pill = screen.getByTestId("live-pill");
    expect(pill.className).not.toContain("bg-garage-green");
    expect(screen.getByTestId("new-count").textContent).toBe("2");
  });

  it("calls onGoLive when the pill is tapped while pinned", () => {
    const onGoLive = vi.fn();
    render(<SwingControlBar {...base} following={false} onGoLive={onGoLive} />);
    fireEvent.click(screen.getByTestId("live-pill"));
    expect(onGoLive).toHaveBeenCalled();
  });

  it("calls onPrev / onNext from the arrows and respects disabled", () => {
    const onPrev = vi.fn(), onNext = vi.fn();
    render(<SwingControlBar {...base} onPrev={onPrev} onNext={onNext} canPrev canNext={false} />);
    fireEvent.click(screen.getByLabelText("Older swing"));
    fireEvent.click(screen.getByLabelText("Newer swing"));
    expect(onPrev).toHaveBeenCalled();
    expect(onNext).not.toHaveBeenCalled(); // disabled
  });

  it("picks a swing from the dropdown", () => {
    const onPickSwing = vi.fn();
    render(<SwingControlBar {...base} onPickSwing={onPickSwing} />);
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "41" } });
    expect(onPickSwing).toHaveBeenCalledWith(41);
  });
});
```

- [ ] **Step 2: Run it — verify it fails**

Run: `npx vitest run src/components/SwingControlBar.test.tsx`
Expected: FAIL — cannot find module `./SwingControlBar`.

- [ ] **Step 3: Implement the component**

```tsx
// web/frontend/src/components/SwingControlBar.tsx
import { cn } from '../lib/utils'
import type { SwingSummary } from '../lib/types'

export type R50State = 'connected' | 'waiting' | 'paused' | 'error'

interface SwingControlBarProps {
  following: boolean          // true = following latest (selectedSwingId === null)
  newCount: number            // swings newer than the pinned one (0 when following)
  r50: R50State
  label: string               // dropdown display for the current swing
  swings: SwingSummary[]      // newest-first
  currentSwingId: number | null
  canPrev: boolean            // an older swing exists
  canNext: boolean            // can step newer / go live (true only when pinned)
  onGoLive: () => void
  onPrev: () => void
  onNext: () => void
  onPickSwing: (id: number) => void
}

const fmtOption = (s: SwingSummary, i: number) =>
  `#${s.id} · ${s.club ?? '—'} · ${new Date(s.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}`
  + (s.has_shot ? ' · R50' : '') + (i === 0 ? ' (latest)' : '')

export function SwingControlBar({
  following, newCount, r50, label, swings, currentSwingId,
  canPrev, canNext, onGoLive, onPrev, onNext, onPickSwing,
}: SwingControlBarProps) {
  // Pill appearance encodes BOTH live/pinned and R50 health.
  const pillClass = following
    ? (r50 === 'waiting'
        ? 'bg-[#E8B931] text-[#0A0D0B] border-[#E8B931]'
        : r50 === 'error' || r50 === 'paused'
          ? 'bg-transparent text-[#5b6b5f] border-[#3a443d]'
          : 'bg-garage-green text-[#0A0D0B] border-garage-green')
    : 'bg-transparent text-garage-green border-garage-green'

  return (
    <div className="flex items-center gap-2 rounded-[14px] border border-[#242C27] bg-[#0d110f] px-2 py-1.5"
         data-testid="swing-control-bar">
      <button
        type="button"
        data-testid="live-pill"
        onClick={() => { if (!following) onGoLive() }}
        aria-label={following ? 'Live (following latest)' : 'Go live'}
        className={cn(
          'relative inline-flex items-center gap-1.5 rounded-full border px-3 min-h-[40px] text-xs font-bold uppercase tracking-wider transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60',
          pillClass,
        )}
      >
        <span className="w-2 h-2 rounded-full bg-current opacity-80" />
        LIVE
        {!following && newCount > 0 && (
          <span data-testid="new-count"
            className="absolute -top-1.5 -right-2 rounded-full border border-garage-green bg-[#0A0D0B] px-1.5 text-[10px] font-extrabold text-garage-green">
            {newCount}
          </span>
        )}
      </button>

      <button type="button" aria-label="Older swing" disabled={!canPrev} onClick={onPrev}
        className="flex items-center justify-center w-10 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] text-[#E7EEE9] disabled:opacity-35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60">‹</button>

      <select
        data-testid="swing-select"
        value={currentSwingId ?? ''}
        onChange={(e) => onPickSwing(Number(e.target.value))}
        aria-label="Select swing"
        className="flex-1 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] px-3 text-sm text-[#E7EEE9] outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60"
      >
        {/* When following, the first option shows "Latest …"; reuse `label`. */}
        {currentSwingId == null && <option value="">{label}</option>}
        {swings.map((s, i) => (
          <option key={s.id} value={s.id}>
            {following && i === 0 ? label : fmtOption(s, i)}
          </option>
        ))}
      </select>

      <button type="button" aria-label="Newer swing" disabled={!canNext} onClick={onNext}
        className="flex items-center justify-center w-10 min-h-[40px] rounded-lg border border-[#242C27] bg-[#121714] text-[#E7EEE9] disabled:opacity-35 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-green/60">›</button>
    </div>
  )
}
```

- [ ] **Step 4: Run it — verify it passes**

Run: `npx vitest run src/components/SwingControlBar.test.tsx`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/SwingControlBar.tsx web/frontend/src/components/SwingControlBar.test.tsx
git commit -m "feat(swing): add SwingControlBar (LIVE/go-live pill + arrows + dropdown)"
```

---

## Task 2: `SwingReplay` "video unavailable" placeholder

Distinguish "no video yet" from "video not kept (pruned)" for a selected swing.

**Files:**
- Modify: `web/frontend/src/components/SwingReplay.tsx`
- Test: `web/frontend/src/components/SwingReplay.test.tsx`

- [ ] **Step 1: Add a test for the custom placeholder**

Append to `web/frontend/src/components/SwingReplay.test.tsx`:

```tsx
it("shows a custom placeholder when src is null and placeholder is given", () => {
  render(<SwingReplay src={null} placeholder="Video not kept for this swing" />);
  expect(screen.getByText("Video not kept for this swing")).toBeInTheDocument();
});
```

(If `render`/`screen` aren't already imported in that file, add `import { render, screen } from "@testing-library/react";`.)

- [ ] **Step 2: Run it — verify it fails**

Run: `npx vitest run src/components/SwingReplay.test.tsx`
Expected: FAIL — default text "No swing video yet." rendered instead.

- [ ] **Step 3: Implement**

In `SwingReplay.tsx`, add `placeholder` to the props interface:

```tsx
  fill?: boolean
  placeholder?: string           // text shown when src is null (default below)
```

Add it to the destructured params: `export function SwingReplay({ src, poseSrc, highlight, seek, impactTime, onTime, onDuration, fill, placeholder }: SwingReplayProps) {`

Replace the no-src branch:

```tsx
        ) : (
          <div className="text-[#8B978F] text-sm">{placeholder ?? 'No swing video yet.'}</div>
        )}
```

- [ ] **Step 4: Run it — verify it passes**

Run: `npx vitest run src/components/SwingReplay.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/SwingReplay.tsx web/frontend/src/components/SwingReplay.test.tsx
git commit -m "feat(swing): SwingReplay custom placeholder for pruned video"
```

---

## Task 3: `SwingScreen` — Following/Pinned state (the core)

Create `SwingScreen.tsx` by copying the **entire current `LiveScreen.tsx`** and applying the changes below. The two-column "captured" body (left: video → stepper → coach; right: ball + body cards) is reused **verbatim** — only data selection, the control bar, and the empty/inline states change.

**Files:**
- Create: `web/frontend/src/pages/SwingScreen.tsx` (from `LiveScreen.tsx`)
- Test: `web/frontend/src/pages/SwingScreen.test.tsx`

- [ ] **Step 1: Copy LiveScreen → SwingScreen and rename the component**

```bash
cp web/frontend/src/pages/LiveScreen.tsx web/frontend/src/pages/SwingScreen.tsx
```

Rename the export and props interface: `LiveScreen` → `SwingScreen`, `LiveScreenProps` → `SwingScreenProps`.

- [ ] **Step 2: Update imports + props**

Update the React import to include `useRef` (the deep-link effect uses it):
`import { useEffect, useMemo, useRef, useState } from 'react'`

Replace the imports line for api to add `getSwing`, `getSwings`:

```tsx
import { getLatestSwing, getSwing, getSwings, getHistory, getBallHistory, mediaUrl } from '../lib/api'
import { SwingControlBar, type R50State } from '../components/SwingControlBar'
import type { SwingDetail, SwingSummary, Benchmark, BallBenchmark, BallRawField } from '../lib/types'
```

Replace the props interface and signature:

```tsx
interface SwingScreenProps {
  playerId: number | null
  sessionId: number | null
  lastSwing: unknown
  activeClub?: string | null
  r50: R50State                       // from App
  deepLinkSwingId?: number | null     // open this swing pinned (one-shot)
  onReconnect: () => void             // navigate to Connect
}

export function SwingScreen({ playerId, sessionId, lastSwing, activeClub = null, r50, deepLinkSwingId = null, onReconnect }: SwingScreenProps) {
```

- [ ] **Step 3: Replace the data-loading block with Following/Pinned selection**

Replace the top of the component (the `useApi` for `data` + the `useEffect(reload)` lines) with:

```tsx
  const [selectedSwingId, setSelectedSwingId] = useState<number | null>(null)
  const following = selectedSwingId === null

  // Reset to Following whenever the player/session context changes.
  useEffect(() => { setSelectedSwingId(null) }, [playerId, sessionId])

  // Deep-link from History/Sessions opens a specific swing pinned (one-shot).
  const lastDeepLink = useRef<number | null>(null)
  useEffect(() => {
    if (deepLinkSwingId != null && deepLinkSwingId !== lastDeepLink.current) {
      lastDeepLink.current = deepLinkSwingId
      setSelectedSwingId(deepLinkSwingId)
    }
  }, [deepLinkSwingId])

  // Swing list (newest-first) for the dropdown/arrows; refetched on each shot.
  const { data: swings } = useApi<SwingSummary[]>(
    () => (playerId ? getSwings(playerId, sessionId ?? undefined, 50) : Promise.resolve([])),
    [playerId, sessionId, lastSwing],
  )
  const swingList = swings ?? []

  // The displayed swing detail: latest when following, else the pinned one.
  const { data, error } = useApi<SwingDetail | null>(
    () => {
      if (!playerId) return Promise.resolve(null)
      return following
        ? getLatestSwing(playerId, sessionId ?? undefined)
        : getSwing(selectedSwingId as number)
    },
    [playerId, sessionId, selectedSwingId, lastSwing],
  )

  // Index of the displayed swing in the newest-first list. idx 0 = latest, so
  // idx itself = number of swings newer than the displayed one (the badge count).
  const displayedId = data?.swing.id ?? null
  const idx = displayedId == null ? -1 : swingList.findIndex((s) => s.id === displayedId)
  const newCount = following ? 0 : Math.max(0, idx)
  const canPrev = idx >= 0 && idx < swingList.length - 1
  const canNext = !following

  const goLive = () => { setSelectedSwingId(null); setVideoTime(0); setSeek(null) }
  const onPrev = () => { if (canPrev) setSelectedSwingId(swingList[idx + 1].id) }
  const onNext = () => {
    if (following) return
    const newer = idx - 1
    if (newer <= 0) goLive()                         // reached latest → go live
    else setSelectedSwingId(swingList[newer].id)
  }
  const controlLabel = following
    ? (data ? `Latest · ${data.swing.club ?? '—'} · ${new Date(data.swing.created_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}` : 'Latest')
    : (data ? `#${data.swing.id} · ${data.swing.club ?? '—'}` : `#${selectedSwingId}`)
```

Keep the existing `videoTime`/`duration`/`seek` state declarations (the `goLive`/`setVideoTime` calls reference them — make sure those `useState` lines remain **above** this block). Keep `cardPhase`, `stepLabel`, `histories`, `ballHistories`, `benchByKey`, `coachContent`, `ballCards`, `videoSrc`/`poseSrc` exactly as in LiveScreen.

- [ ] **Step 4: Replace `status` + the waiting branch with R50-aware inline states**

Replace `const status: 'waiting' | 'captured' = data ? 'captured' : 'waiting'` with nothing (remove it) and replace the `<AnimatePresence>` waiting branch condition. The "no swing to show" case now depends on R50:

```tsx
      <AnimatePresence mode="wait">
        {!data ? (
          <motion.div key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="flex-1 flex flex-col items-center justify-center border-2 border-dashed border-[#242C27] rounded-[24px] bg-[#0A0D0B]/50 text-center px-6">
            {r50 === 'error' || r50 === 'paused' ? (
              <>
                <div className="w-3 h-3 rounded-full bg-garage-red mb-5" />
                <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">R50 not connected</h2>
                <p className="text-[#8B978F] mb-4">Shots won't record until the R50 reconnects.</p>
                <button onClick={onReconnect}
                  className="rounded-full border border-garage-red/50 bg-garage-red/10 px-5 py-2.5 text-sm text-garage-red min-h-[44px] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-garage-red/60">
                  Reconnect →
                </button>
              </>
            ) : (
              <>
                <div className="w-16 h-16 rounded-full bg-[#121714] border border-[#242C27] flex items-center justify-center mb-6 relative">
                  <div className="absolute inset-0 rounded-full border-2 border-garage-green animate-ping opacity-20" />
                  <div className="w-3 h-3 rounded-full bg-garage-green animate-pulse" />
                </div>
                <h2 className="text-2xl font-semibold text-[#E7EEE9] mb-2">Waiting for your R50</h2>
                <p className="text-[#8B978F]">Step up and take a swing. Data will appear here automatically.</p>
              </>
            )}
          </motion.div>
        ) : (
          <motion.div key="captured" initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            className="flex-1 min-h-0 flex flex-col lg:flex-row gap-3">
            {/* LEFT (~46%): control bar → video → position stepper → AI coach read. */}
            <div className="flex flex-col gap-3 min-h-0 lg:basis-[46%] lg:flex-none">
              <SwingControlBar
                following={following} newCount={newCount} r50={r50}
                label={controlLabel} swings={swingList} currentSwingId={displayedId}
                canPrev={canPrev} canNext={canNext}
                onGoLive={goLive} onPrev={onPrev} onNext={onNext}
                onPickSwing={(id) => setSelectedSwingId(id)} />

              <div className="flex-[4] min-h-0">
                <SwingReplay src={videoSrc} poseSrc={poseSrc} highlight fill seek={seek} impactTime={impactTime}
                  placeholder="Video not kept for this swing"
                  onDuration={setDuration}
                  onTime={setVideoTime} />
              </div>
              {/* ...keep the existing stepper + coach blocks verbatim... */}
```

Leave the rest of the captured branch (stepper, coach, right-hand metrics column) **exactly** as it is in LiveScreen.

- [ ] **Step 5: Write the SwingScreen test**

```bash
cp web/frontend/src/pages/LiveScreen.test.tsx web/frontend/src/pages/SwingScreen.test.tsx
```

Then rewrite it:

```tsx
// web/frontend/src/pages/SwingScreen.test.tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import type { SwingDetail, SwingSummary } from "../lib/types";

vi.mock("../lib/api", () => ({
  getLatestSwing: vi.fn(),
  getSwing: vi.fn(),
  getSwings: vi.fn(),
  getHistory: vi.fn(),
  getBallHistory: vi.fn(),
  mediaUrl: (p: string) => `/media/${p}`,
}));

import { SwingScreen } from "./SwingScreen";
import * as api from "../lib/api";

function mkDetail(id: number, opts: Partial<SwingDetail["swing"]> = {}, withVideo = true): SwingDetail {
  return {
    swing: { id, session_id: 1, player_id: 1, created_at: "2024-01-01T10:00:00Z",
      source_video_path: null, view_layout: null, fps: null, width: null, height: null,
      club: "7 Iron", notes: null, shot_id: id === 42 ? 99 : null, ...opts },
    metrics: [],
    benchmarks: [{ name: "shoulder_tilt_deg", context: "impact", value: 38, unit: "deg",
      target: 36, delta: 2, comparable: true, reason: null, direction: "higher", zone: "green", state: "ok" }],
    ball_benchmarks: [{ key: "ball_speed", label: "Ball Speed", unit: "mph", value: 142,
      target: 161, delta: -19, near: false, direction: "higher", zone: "red" }],
    ball_raw: [],
    moments: [{ id: 1, swing_id: id, kind: "impact", view: null, frame_index: 30, time_s: 1.0 }],
    shot: null, coaching: [],
    media: withVideo ? [{ id: 1, swing_id: id, kind: "annotated_video", path: `${id}.mp4`, meta: null }] : [],
  };
}
const summaries: SwingSummary[] = [
  { id: 42, created_at: "2024-01-01T10:02:00Z", club: "7 Iron", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  { id: 41, created_at: "2024-01-01T10:01:00Z", club: "Driver", has_shot: true, hip_sway_in: null, shoulder_tilt_deg: null },
  { id: 40, created_at: "2024-01-01T10:00:00Z", club: "PW", has_shot: false, hip_sway_in: null, shoulder_tilt_deg: null },
];

const props = { playerId: 1, sessionId: 1, lastSwing: null, activeClub: "7 Iron",
  r50: "connected" as const, deepLinkSwingId: null, onReconnect: vi.fn() };

beforeEach(() => {
  vi.mocked(api.getLatestSwing).mockResolvedValue(mkDetail(42));
  vi.mocked(api.getSwing).mockImplementation((id: number) => Promise.resolve(mkDetail(id, {}, id !== 40)));
  vi.mocked(api.getSwings).mockResolvedValue(summaries);
  vi.mocked(api.getHistory).mockResolvedValue({ player: 1, metric: "shoulder_tilt_deg", context: "impact", points: [] });
  vi.mocked(api.getBallHistory).mockResolvedValue({ player: 1, metric: "ball_speed", club: "7 Iron", target: 161, points: [] });
});

describe("SwingScreen", () => {
  it("follows the latest swing by default", async () => {
    render(<SwingScreen {...props} />);
    expect(await screen.findByText("38")).toBeInTheDocument(); // body card from latest
    expect(api.getLatestSwing).toHaveBeenCalled();
  });

  it("pins a past swing when picked, loading getSwing", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "41" } });
    await waitFor(() => expect(api.getSwing).toHaveBeenCalledWith(41));
  });

  it("shows the new-shot count badge when pinned behind newer swings", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } }); // 2 newer
    expect(await screen.findByTestId("new-count")).toHaveTextContent("2");
  });

  it("Go Live returns to following and clears the badge", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } });
    await screen.findByTestId("new-count");
    fireEvent.click(screen.getByTestId("live-pill"));
    await waitFor(() => expect(screen.queryByTestId("new-count")).toBeNull());
  });

  it("shows the 'video not kept' placeholder for a pinned swing with no video", async () => {
    render(<SwingScreen {...props} />);
    await screen.findByText("38");
    fireEvent.change(screen.getByTestId("swing-select"), { target: { value: "40" } }); // mkDetail(40) has no video
    expect(await screen.findByText("Video not kept for this swing")).toBeInTheDocument();
  });

  it("shows the R50-disconnected empty state with a Reconnect button", async () => {
    vi.mocked(api.getLatestSwing).mockResolvedValue(null);
    const onReconnect = vi.fn();
    render(<SwingScreen {...props} r50="error" onReconnect={onReconnect} />);
    const btn = await screen.findByText(/Reconnect/);
    fireEvent.click(btn);
    expect(onReconnect).toHaveBeenCalled();
  });

  it("opens deep-linked swing pinned", async () => {
    render(<SwingScreen {...props} deepLinkSwingId={41} />);
    await waitFor(() => expect(api.getSwing).toHaveBeenCalledWith(41));
  });
});
```

- [ ] **Step 6: Run the SwingScreen + control-bar tests**

Run: `npx vitest run src/pages/SwingScreen.test.tsx src/components/SwingControlBar.test.tsx`
Expected: PASS. (Fix any prop/type drift surfaced here.)

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/pages/SwingScreen.tsx web/frontend/src/pages/SwingScreen.test.tsx
git commit -m "feat(swing): SwingScreen with Following/Pinned state model"
```

---

## Task 4: Topbar — remove R50 pill, add Session-button status dot

**Files:**
- Modify: `web/frontend/src/components/Topbar.tsx`

- [ ] **Step 1: Widen the `r50Status` union**

In `TopbarProps`, change:

```tsx
  r50Status: 'connected' | 'waiting' | 'paused' | 'error'
```

- [ ] **Step 2: Remove the R50 status pill block**

Delete the entire `<div className="flex items-center space-x-2 bg-[#121714] ... rounded-full ...">…</div>` block that renders the R50 dot + "R50 Connected/Waiting/Paused" text + `<Wifi/>`. Remove the now-unused `Wifi` import.

- [ ] **Step 3: Add a status dot inside the Start/End Session button**

Inside the session `<button>`, before the `{sessionActive ? … : …}` content, add:

```tsx
          <span className={cn('w-2.5 h-2.5 rounded-full',
            r50Status === 'connected' ? 'bg-garage-green'
              : r50Status === 'waiting' ? 'bg-garage-amber'
                : r50Status === 'paused' ? 'bg-[#8B978F]' : 'bg-garage-red')}
            title={`R50: ${r50Status}`} />
```

- [ ] **Step 4: Typecheck/build**

Run: `npm run build`
Expected: builds clean (TS happy with the widened union; App still passes a valid value after Task 6).

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/components/Topbar.tsx
git commit -m "feat(swing): move R50 status to a dot on the Session button"
```

---

## Task 5: Sidebar — rename live→swing, remove review, gear badge

**Files:**
- Modify: `web/frontend/src/components/Sidebar.tsx`

- [ ] **Step 1: Update props + nav items**

Add `r50Error?: boolean` to `SidebarProps`. Change the `navItems` array: rename the first item to `{ id: 'swing', label: 'Swing', icon: Activity }` and **delete** the `{ id: 'review', ... }` entry. Remove the now-unused `Video` import.

- [ ] **Step 2: Render the gear badge**

On the bottom gear `<button>` (the `connect` one), add inside it (after the `<Settings/>`), a conditional badge:

```tsx
          {r50Error && (
            <span className="absolute top-2 right-2 w-2.5 h-2.5 rounded-full bg-garage-red ring-2 ring-[#0A0D0B]"
              aria-label="R50 connection problem" />
          )}
```

(The button is already `relative`.)

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add web/frontend/src/components/Sidebar.tsx
git commit -m "feat(swing): rename Live→Swing, drop Review, add R50 gear badge"
```

---

## Task 6: App — route SwingScreen, remove Review, deep-link + R50 plumbing

**Files:**
- Modify: `web/frontend/src/App.tsx`

- [ ] **Step 1: Swap imports**

Remove `import { LiveScreen } ...` and `import { ReviewScreen } ...`; add `import { SwingScreen } from './pages/SwingScreen'`.

- [ ] **Step 2: Default tab + deep-link state**

Change `useState('live')` → `useState('swing')`. Remove the `reviewSwingId` state + its `useEffect` (lines that call `getLatestSwing` to set `reviewSwingId`) and drop `getLatestSwing` from the api import if now unused. Add:

```tsx
  const [pinnedSwingId, setPinnedSwingId] = useState<number | null>(null)
  const openSwing = (id: number) => { setPinnedSwingId(id); setActiveTab('swing') }
```

- [ ] **Step 3: Compute the 4-state R50 value**

Replace the `r50Status` computation:

```tsx
  const st = capture.status?.status
  const r50: 'connected' | 'waiting' | 'paused' | 'error' =
    st === 'connected' ? 'connected'
      : st === 'paused' ? 'paused'
        : (capture.status?.last_error || st === 'stopped') ? 'error'
          : 'waiting'
```

Pass `r50Status={r50}` to `<Topbar>` and add `r50Error={r50 === 'error'}` to `<Sidebar>`.

- [ ] **Step 4: Replace the live/review routes**

Replace the `activeTab === 'live'` and `activeTab === 'review'` blocks with a single:

```tsx
          {activeTab === 'swing' && (
            <SwingScreen
              playerId={activePlayerId}
              sessionId={activeSessionId}
              lastSwing={lastSwing}
              activeClub={capture.status?.active_club ?? null}
              r50={r50}
              deepLinkSwingId={pinnedSwingId}
              onReconnect={() => setActiveTab('connect')}
            />
          )}
```

- [ ] **Step 5: Pass `onOpenSwing` to History + Sessions**

```tsx
          {activeTab === 'history' && <HistoryScreen playerId={activePlayerId} onOpenSwing={openSwing} />}
          {activeTab === 'sessions' && (
            <SessionsScreen activeSessionId={activeSessionId} onOpenSwing={openSwing} />
          )}
```

- [ ] **Step 6: Build**

Run: `npm run build`
Expected: clean (Sessions/History props added in Task 7; if building before Task 7, temporarily expect TS errors there — do Task 7 next, then build).

- [ ] **Step 7: Commit**

```bash
git add web/frontend/src/App.tsx
git commit -m "feat(swing): route SwingScreen, drop Review, wire deep-link + R50 state"
```

---

## Task 7: Deep-link wiring in Sessions + History

**Files:**
- Modify: `web/frontend/src/pages/SessionsScreen.tsx`
- Modify: `web/frontend/src/pages/HistoryScreen.tsx`

- [ ] **Step 1: Sessions — add prop + latest-swing id, wire "View Swings"**

In `SessionVM` add `latestSwingId: number | null`. In the `.map`, compute it from the loaded detail (swings are returned newest-first by the API; guard for empty):

```tsx
        latestSwingId: d && d.swings.length ? d.swings[0].id : null,
```

Add to props: `interface SessionsScreenProps { activeSessionId: number | null; onOpenSwing: (id: number) => void }` and destructure `onOpenSwing`. Make the "View Swings" button open it:

```tsx
              <button
                onClick={() => session.latestSwingId != null && onOpenSwing(session.latestSwingId)}
                disabled={session.latestSwingId == null}
                className="flex items-center space-x-2 text-[#E7EEE9] bg-[#1A211D] group-hover:bg-garage-green group-hover:text-[#0A0D0B] px-5 py-3 rounded-full font-medium transition-all min-h-[44px] disabled:opacity-40">
                <Video className="w-4 h-4" />
                <span>View Swings</span>
                <ChevronRight className="w-4 h-4" />
              </button>
```

- [ ] **Step 2: History — add prop, make hero-chart points open their swing**

Add to props: `interface HistoryScreenProps { playerId: number | null; onOpenSwing: (id: number) => void }` and destructure `onOpenSwing`. Carry `swing_id` into the chart data:

```tsx
  const chartData = heroPoints.map((p) => ({
    date: useTimeAxis ? timeOfDay(p.created_at) : shortDate(p.created_at),
    value: p.value,
    swingId: p.swing_id,
  }))
```

On the `<Line>`, add an `activeDot` click handler:

```tsx
                  activeDot={{
                    r: 8, fill: '#79BC30', stroke: '#0A0D0B', strokeWidth: 3,
                    style: { cursor: 'pointer' },
                    onClick: (_: unknown, payload: { payload?: { swingId?: number } }) => {
                      const id = payload?.payload?.swingId
                      if (id != null) onOpenSwing(id)
                    },
                  }}
```

(If recharts' payload typing is awkward, type the handler `(e: any, p: any)` and read `p?.payload?.swingId` — recharts passes the datum under `payload.payload`.)

- [ ] **Step 3: Update HistoryScreen test for the new required prop**

In `src/pages/HistoryScreen.test.tsx`, pass `onOpenSwing={() => {}}` to every `<HistoryScreen ... />` render so the required prop is satisfied.

- [ ] **Step 4: Build + run touched tests**

Run: `npm run build`
Expected: clean.
Run: `npx vitest run src/pages/HistoryScreen.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/frontend/src/pages/SessionsScreen.tsx web/frontend/src/pages/HistoryScreen.tsx web/frontend/src/pages/HistoryScreen.test.tsx
git commit -m "feat(swing): deep-link from Sessions + History into Swing"
```

---

## Task 8: Delete the old screens

**Files:**
- Delete: `web/frontend/src/pages/ReviewScreen.tsx`, `web/frontend/src/pages/ReviewScreen.test.tsx`
- Delete: `web/frontend/src/pages/LiveScreen.tsx`, `web/frontend/src/pages/LiveScreen.test.tsx`

- [ ] **Step 1: Confirm no remaining imports**

Run: `grep -rn "ReviewScreen\|LiveScreen" web/frontend/src`
Expected: no results (App was updated in Task 6).

- [ ] **Step 2: Delete the files**

```bash
git rm web/frontend/src/pages/ReviewScreen.tsx web/frontend/src/pages/ReviewScreen.test.tsx \
       web/frontend/src/pages/LiveScreen.tsx web/frontend/src/pages/LiveScreen.test.tsx
```

- [ ] **Step 3: Check for dead components**

Run: `grep -rn "PhaseTimeline" web/frontend/src`
If `PhaseTimeline` is now only referenced by the deleted ReviewScreen (no other importers), also `git rm web/frontend/src/components/PhaseTimeline.tsx` and its test (`PhaseTimeline.test.tsx`) — but first confirm `phase.ts` doesn't import `PHASE_LABELS` from it; if it does, leave `PhaseTimeline.tsx` in place (it exports `PHASE_LABELS`). Decision rule: keep the file if anything outside the deleted screens imports from it.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "chore(swing): remove old Live + Review screens"
```

---

## Task 9: Full verification

- [ ] **Step 1: Whole frontend test suite**

Run: `npx vitest run`
Expected: all suites pass (SwingScreen, SwingControlBar, SwingReplay, HistoryScreen, others unchanged).

- [ ] **Step 2: Production build**

Run: `npm run build`
Expected: built, no TS errors.

- [ ] **Step 3: Browser smoke (reseed if needed, server running)**

From repo root: `python -m web.backend.seed_demo` (if the dev DB is stale), ensure the backend is running, then load `http://127.0.0.1:8000/`. Verify:
- Sidebar shows **Swing** (not Live/Review).
- Default = Following (solid green LIVE pill); the latest swing shows.
- Pick an older swing in the dropdown → pins; if it's behind newer swings, the LIVE pill shows a count badge; the dropdown reads `#id · club`.
- Tap the LIVE pill → returns to latest, badge clears.
- `‹ ›` step through swings; `›` at the newest returns to live.
- Header has **no R50 pill**; the Session button has a colored status dot.
- Sessions "View Swings" and a History chart point both open the Swing screen pinned.

- [ ] **Step 4: Commit any fixes, then done**

```bash
git add -A && git commit -m "test(swing): verify unified Swing screen" && git push
```

---

## Notes / non-goals
- **Video retention/pruning** is a separate future spec. This plan only adds the *graceful* "Video not kept for this swing" placeholder (Task 2/3) for swings whose video is already absent.
- No backend changes: all endpoints used (`getSwings`, `getSwing`, `getLatestSwing`, capture status) already exist.
- The two-column captured-state body (stepper, coach, metric columns) is reused unchanged from LiveScreen — do not redesign it here.
```
