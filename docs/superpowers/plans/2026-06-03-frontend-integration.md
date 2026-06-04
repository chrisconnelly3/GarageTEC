# Frontend Integration (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `web/frontend/` to TypeScript + Tailwind CSS and port the MagicPatterns design (all 7 screens + components + tokens) so `npm run build` succeeds and the app renders the full dark+green UI using MagicPatterns' hardcoded demo data.

**Architecture:** This is a frontend **port**, not a feature build — we swap the plain-JS Vite scaffold for a TypeScript + Tailwind Vite app and drop in MagicPatterns' self-contained React components (Sidebar/Topbar shell + 7 screens + shared UI primitives + design tokens). MP's components are NOT shadcn-CLI components — they are standalone `.tsx` files that depend only on Tailwind + a `cn()` helper + `framer-motion`/`lucide-react`/`recharts`, so there is **no shadcn init**. We preserve the data-layer files (`api`, `useEvents`, `useCapture`) untouched for Phase 2 wiring and do not touch `web/backend/`.

**Tech Stack:** React 18 · TypeScript · Vite 5 · Tailwind CSS 3 · PostCSS + Autoprefixer · framer-motion · lucide-react · clsx + tailwind-merge (`cn()`) · recharts · vitest + Testing Library (smoke only).

---

## SCOPE — read this before starting

**IN SCOPE (Phase 1):**
- Migrate the Vite app to TypeScript + Tailwind.
- Pull every MagicPatterns source file via the MagicPatterns MCP and write it into `web/frontend/src/` at the matching path, fixing imports and stripping MP-canvas-only bits.
- Wire `src/App.tsx` to the ported Sidebar/Topbar + 7 screens with tab routing (as in MP's `App.tsx`, minus `useScreenInit`).
- Get `npm install` + `npm run build` green and one lightweight vitest smoke test passing.

**OUT OF SCOPE (this is Phase 2 — DO NOT do it here):**
- **Real-data wiring is explicitly Phase 2.** Do NOT connect the ported screens to our `/api/*` endpoints or the `/events` SSE stream. **Keep MagicPatterns' hardcoded demo data exactly as shipped.** The screens render MP's fake golfers, fake metrics, and fake swings. We only preserve `api.ts`/`useEvents.js`/`useCapture.js` on disk (unused for now) so Phase 2 can wire them.
- No backend changes whatsoever (`web/backend/` is read-only here). Backend Python tests must stay green by virtue of not being touched.
- No `react-router-dom` routing rework beyond what MP's tab-based `App.tsx` does (MP uses local tab state, not URL routes — that's fine for Phase 1).

---

## File Structure

Target `web/frontend/` layout after this plan (preserved files marked, deleted files listed in Task 7):

```
web/frontend/
  package.json            # rewritten: + TS/Tailwind/MP deps, "build" runs tsc + vite
  tsconfig.json           # NEW
  tsconfig.node.json      # NEW (for vite.config.ts)
  vite.config.ts          # was vite.config.js — ported, proxy + vitest config kept
  tailwind.config.js      # NEW (from MP, adapted content globs)
  postcss.config.js       # NEW
  index.html              # entry script -> /src/main.tsx
  .gitignore              # unchanged (node_modules/, dist/ already ignored)
  src/
    main.tsx              # was main.jsx — mounts <App/>, imports ./index.css
    index.css             # was styles.css — REPLACED by MP's index.css (@tailwind + tokens)
    App.tsx               # was App.jsx — REPLACED by ported MP shell (Sidebar/Topbar/tabs)
    setupTests.ts         # was setupTests.js
    lib/
      utils.ts            # NEW — MP's cn() helper
    components/           # MP components (13 .tsx), REPLACING old GlobalBar/MetricCard/Sidebar
      Tabs.tsx
      Slider.tsx
      Progress.tsx
      Card.tsx
      Avatar.tsx
      Badge.tsx
      Button.tsx
      Sidebar.tsx
      Topbar.tsx
      MetricCard.tsx
      AIInsightCard.tsx
      SwingReplay.tsx
      BallClubStrip.tsx
      MetricCard.test.tsx # NEW smoke test (the ONLY test we add)
    pages/                # MP screens (7 .tsx), REPLACING old plain-JS pages
      LiveScreen.tsx
      ReviewScreen.tsx
      HistoryScreen.tsx
      SessionsScreen.tsx
      PlayersScreen.tsx
      SyncScreen.tsx
      ConnectScreen.tsx
    # ---- PRESERVED (Phase 2 wiring; left untouched except api.js->api.ts rename) ----
    api.ts                # was api.js (rename only; content unchanged)
    useEvents.js          # PRESERVED as-is
    useCapture.js         # PRESERVED as-is
```

> `node_modules/` and `dist/` stay gitignored (already in `web/frontend/.gitignore`) — never commit them.

---

## MagicPatterns source (pulled by the build agent, NOT pre-bundled)

- **editorId:** `vbsfbzbwztgl3x464k7fdi`
- **artifactId:** `ffefb52b-4345-4d52-a330-72e7a0df0c5c`
- **27 files**, but **EXCLUDE/SKIP `canvas.manifest.js` and `useScreenInit.js`** (MP-canvas-only). We use a simple `App` entry instead.
- **Files to pull and where they land:**
  - `index.css` → `src/index.css`
  - `tailwind.config.js` → `tailwind.config.js`
  - `lib/utils.ts` → `src/lib/utils.ts`
  - `App.tsx` → `src/App.tsx` (port: strip `useScreenInit`/canvas wiring; keep tab state)
  - `index.tsx` → reference only for mount logic; we author `src/main.tsx` ourselves (Task 5)
  - `components/{Tabs,Slider,Progress,Card,Avatar,Badge,Button,Sidebar,Topbar,MetricCard,AIInsightCard,SwingReplay,BallClubStrip}.tsx` → `src/components/<same>.tsx`
  - `pages/{Live,Review,History,Sessions,Players,Sync,Connect}Screen.tsx` → `src/pages/<same>.tsx`

**MCP access (do this in Task 6, before writing any ported file):**
1. Load the MagicPatterns MCP tools via ToolSearch, e.g. `ToolSearch("magicpatterns read_artifact_files get_artifact")`. Expect `read_artifact_files`, `get_artifact`, `get_editor_id_from_url`, etc.
2. Optionally call `get_artifact(artifactId)` to confirm the file list.
3. For each file, call `read_artifact_files(artifactId, fileNames=[...])` (batch several names per call) to get raw content.
4. Write each file to its target path; fix imports (see Task 6 rules).
5. **If the MP MCP is unreachable or returns an error, STOP immediately and report** "Cannot access MagicPatterns MCP — orchestrator must supply the 25 files (editorId vbsfbzbwztgl3x464k7fdi / artifactId ffefb52b-4345-4d52-a330-72e7a0df0c5c)." Do not fabricate component contents.

---

## Tasks

### Task 1 — Branch + baseline

- [ ] Confirm working tree is clean (`git status`). If on `main`, create a feature branch (e.g. `frontend-integration-phase1`). Do NOT commit until the orchestrator asks.
- [ ] Record the baseline so you can prove backend stays green later: from repo root run the backend tests once and note they pass:
  - Command: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/tests -q`
  - Expected: all pass (this is the "before" snapshot; we will NOT touch backend).

### Task 2 — Rewrite `package.json` (full content)

- [ ] Replace `web/frontend/package.json` with the following. Note `build` now runs `tsc` (typecheck) then `vite build`; the smoke test stays on vitest.

```json
{
  "name": "garagetec-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "framer-motion": "^11.3.0",
    "lucide-react": "^0.408.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "recharts": "^2.12.0",
    "tailwind-merge": "^2.4.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.4.0",
    "@testing-library/react": "^16.0.0",
    "@types/node": "^20.14.0",
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.19",
    "jsdom": "^24.1.0",
    "postcss": "^8.4.39",
    "tailwindcss": "^3.4.6",
    "typescript": "^5.5.3",
    "vite": "^5.4.0",
    "vitest": "^2.0.0"
  }
}
```

> Note: `react-router-dom` is intentionally **dropped** — MP's `App.tsx` uses local tab state, not URL routing. (If, after pulling MP files, any ported file still imports `react-router-dom`, add it back to deps; but the canonical MP shell does not.)

### Task 3 — TypeScript config (full content)

- [ ] Create `web/frontend/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": false,
    "noUnusedParameters": false,
    "noFallthroughCasesInSwitch": true,
    "allowJs": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

> `allowJs: true` lets the preserved `useEvents.js` / `useCapture.js` coexist without conversion. `noUnusedLocals/Parameters` are **off** so MP's ported components (which may have unused imports) don't fail the typecheck gate — this is a port, not new code. `@/*` path alias is provided in case MP files use it; if MP uses relative imports only, the alias is harmless.

- [ ] Create `web/frontend/tsconfig.node.json` (for the Vite config file itself):

```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

### Task 4 — Build tooling: `vite.config.ts`, `postcss.config.js`, `tailwind.config.js` (full content)

- [ ] Delete `web/frontend/vite.config.js` and create `web/frontend/vite.config.ts` (preserves the dev proxy + vitest config from the old file; adds the `@` alias):

```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "./",
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  build: { outDir: "dist" },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/events": "http://localhost:8000",
      "/media": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/setupTests.ts"],
  },
});
```

- [ ] Create `web/frontend/postcss.config.js`:

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] Create `web/frontend/tailwind.config.js` (Task 6 pulls MP's version; until then use this as the base/fallback so the build is not blocked — **after pulling MP's `tailwind.config.js`, MERGE its `theme.extend` (the green tokens, radii, glow shadows, fonts) into this `content`/`darkMode` skeleton**). The `content` globs and `darkMode` MUST be:

```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
    extend: {
      // <-- Merge MagicPatterns' theme.extend here (colors incl. GarageTEC
      //     green #84CE39 / #78BA30, backgrounds #0A0D0B / #121714 / #1A211D,
      //     border #242C27, text #E7EEE9 / #8B978F, radii 18px/12px,
      //     green-glow boxShadow, fontFamily Inter). Keep MP's exact token
      //     names so its className strings resolve.
    },
  },
  plugins: [],
};
```

> **Important:** MP's own `tailwind.config.js` may use a different `content` path (MP-canvas paths). Always overwrite `content` with `["./index.html", "./src/**/*.{ts,tsx,js,jsx}"]` and `darkMode: "class"` (or `"media"` if MP forces dark globally — but `"class"` + a `dark`/root class set in `index.css` or `main.tsx` is safest). Keep everything under `theme.extend` from MP verbatim.

### Task 5 — App entry: `index.html`, `src/main.tsx`, `src/index.css` placeholder, `src/setupTests.ts`

- [ ] Edit `web/frontend/index.html`: change the script src from `/src/main.jsx` to `/src/main.tsx`. (Optionally add `class="dark"` to `<html>` if MP relies on a `dark` class and does not set it elsewhere.)

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>GarageTEC</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] Delete `web/frontend/src/main.jsx` and create `web/frontend/src/main.tsx` (no BrowserRouter — MP uses tab state, not routes):

```tsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

- [ ] Delete `web/frontend/src/styles.css`. Create a temporary `web/frontend/src/index.css` with at minimum the Tailwind directives (Task 6 OVERWRITES this with MP's full `index.css`, which itself must begin with these three directives — verify they are present after the pull, prepend them if MP omitted them):

```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

- [ ] Delete `web/frontend/src/setupTests.js` and create `web/frontend/src/setupTests.ts`:

```ts
import "@testing-library/jest-dom";
```

### Task 6 — Pull + port the MagicPatterns components, pages, tokens, and `cn()` helper

- [ ] **Load the MP MCP tools** via ToolSearch (`ToolSearch("magicpatterns read_artifact_files get_artifact")`). If unavailable, STOP and report (see "MCP access" above).
- [ ] Pull `lib/utils.ts` → write to `web/frontend/src/lib/utils.ts` (the `cn()` helper using `clsx` + `tailwind-merge`). If for any reason it is empty/missing, author the canonical version:

```ts
import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

- [ ] Pull `index.css` → **overwrite** `web/frontend/src/index.css` (must keep the three `@tailwind` directives at the top; this file carries the CSS-variable color tokens / font setup).
- [ ] Pull `tailwind.config.js` → merge its `theme.extend` into `web/frontend/tailwind.config.js` per Task 4 (keep our `content` + `darkMode`).
- [ ] Pull the **13 components** and write each to `web/frontend/src/components/<Name>.tsx`:
      `Tabs, Slider, Progress, Card, Avatar, Badge, Button, Sidebar, Topbar, MetricCard, AIInsightCard, SwingReplay, BallClubStrip`.
- [ ] Pull the **7 pages** and write each to `web/frontend/src/pages/<Name>Screen.tsx`:
      `Live, Review, History, Sessions, Players, Sync, Connect`.
- [ ] **Per-file porting rules** (apply while writing each file):
  - Remove any `import ... from './useScreenInit'` / `useScreenInit(...)` calls and any reference to `canvas.manifest`. These are MP-canvas-only.
  - Fix import paths to match our layout: components import siblings as `./Card`, `../lib/utils` (or `@/lib/utils`), pages import `../components/<X>`. Keep MP's choice (relative vs `@/`) as long as it resolves — the `@` alias is configured in both `vite.config.ts` and `tsconfig.json`.
  - **Do NOT alter MP's hardcoded demo data** (golfers, metrics, swings). That data IS the Phase-1 render. (Phase 2 replaces it.)
  - If a file imports an icon from `lucide-react`, a chart from `recharts`, or animation from `framer-motion` — those deps are in `package.json` (Task 2). If a ported file imports something NOT in our deps, add it to `package.json` dependencies and note it in the final report.
  - Strip MP-canvas comment banners if present; keep the component logic verbatim otherwise.

### Task 7 — Wire `src/App.tsx` (ported shell) + remove obsolete scaffolded files

- [ ] Pull MP's `App.tsx` → write `web/frontend/src/App.tsx`. Port it to:
  - Render the `Sidebar` + `Topbar` shell and switch the 7 `*Screen` pages via MP's tab state (the `activeTab` / `setActiveTab` pattern from MP's `App.tsx`).
  - **Remove** `useScreenInit` and any `canvas.manifest` wiring.
  - Use MP's demo data / default selected tab (Live). No `/api/*` calls, no SSE — Phase 1 is demo-data only.
- [ ] **Delete the obsolete plain-JS scaffold** that the MP versions replace:
  - `src/App.jsx`
  - `src/pages/Live.jsx`, `Connect.jsx`, `History.jsx`, `Players.jsx`, `Session.jsx`, `SwingReview.jsx`, `SyncFix.jsx`
  - `src/components/GlobalBar.jsx`, `src/components/GlobalBar.test.jsx`
  - `src/components/MetricCard.jsx`, `src/components/MetricCard.test.jsx`
  - `src/components/Sidebar.jsx`
- [ ] **Rename** `src/api.js` → `src/api.ts` (content unchanged — it is plain JS that is valid TS; `allowJs` covers it either way, but `.ts` is cleaner). **KEEP** `src/useEvents.js` and `src/useCapture.js` as-is (they stay `.js`; preserved for Phase 2; currently unused — that's expected). Note: `useCapture.js` imports from `./api`, which still resolves after the rename.
- [ ] Verify nothing in the new `App.tsx`/pages imports the deleted scaffold files.

### Task 8 — Smoke test (the only test we add)

- [ ] Create `web/frontend/src/components/MetricCard.test.tsx` — a lightweight render smoke test against the **ported** `MetricCard` using demo-shaped props. **First inspect the ported `MetricCard.tsx` to learn its real prop names** (MP's prop shape differs from the old scaffold's `{name,value,unit,vsBaseline}`), then assert a value renders. Template (adjust prop names/labels to match the ported component):

```tsx
import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MetricCard } from "./MetricCard"; // or `default` — match the ported export style

describe("MetricCard", () => {
  it("renders a metric value with demo props", () => {
    render(
      // TODO: fill props to match ported MetricCard's interface, e.g.:
      <MetricCard label="Shoulder Tilt" value={38} unit="°" delta={2.1} />
    );
    expect(screen.getByText(/Shoulder Tilt/i)).toBeInTheDocument();
  });
});
```

> If the ported `MetricCard` is a default export, import it as default. The point of this test is a build-adjacent render smoke check, not coverage — keep it to one passing assertion.

### Task 9 — GATE: install, typecheck+build, smoke test, backend green

Run each command from `web/frontend/` (the directory persists between Bash calls is NOT guaranteed in the agent harness — use full paths / `npm --prefix`). Use the full Node path if `npm` is not on PATH: `& 'C:\Program Files\nodejs\npm.cmd' ...`.

- [ ] **Install** — must succeed with no peer-dep errors that abort:
  - Command: `npm install --prefix web/frontend`
  - Expected: dependencies resolve; `node_modules/` created (and stays gitignored).
- [ ] **Build (tsc + vite)** — the primary gate:
  - Command: `npm run build --prefix web/frontend`
  - Expected: `tsc -b` reports no type errors, then `vite build` writes `web/frontend/dist/` (`index.html` + hashed JS/CSS). Exit code 0.
  - If `tsc` fails on a ported MP file, FIX the type error minimally (add a type, widen a prop, `// @ts-expect-error` only as a last resort with a comment) — do NOT loosen `strict` globally beyond the `noUnusedLocals/Parameters: false` already set.
- [ ] **Smoke test** — must pass:
  - Command: `npm run test --prefix web/frontend`
  - Expected: the single `MetricCard` smoke test passes (1 passed).
- [ ] **Backend still green** (prove no backend regression — we changed nothing there):
  - Command: `& 'C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe' -m pytest web/backend/tests -q`
  - Expected: same pass count as the Task 1 baseline.
- [ ] **Static-mount sanity** (confirm FastAPI will serve the new dist): `web/backend/app.py` mounts `web/frontend/dist` at `/` when it exists. After the build, confirm `web/frontend/dist/index.html` exists. (Optional deeper check: start `uvicorn web.backend.app:app`, GET `/`, confirm it returns the built `index.html`; then stop it. Not required if dist is present — the mount is unconditional on `dist.is_dir()`.)

### Task 10 — Final verification + report (no commit)

- [ ] Re-run the SKILL verification-before-completion checklist: every gate command above was actually run and its output observed (not assumed).
- [ ] Confirm `git status` shows: new TS/Tailwind config + `src/**` MP files; deleted old `.jsx` scaffold; `node_modules/` and `dist/` NOT staged (still ignored).
- [ ] Do **NOT** commit and do **NOT** run any `git` mutation — leave the tree for the orchestrator to review.
- [ ] Report: confirm Phase-1 scope met (full dark+green UI renders with MP demo data; real-data wiring deferred to Phase 2), list any deps added beyond the spec'd set, and flag any MP file that needed manual type fixes.

---

## Notes / Risks

- **Demo data only (restated):** the app intentionally shows MagicPatterns' fake golfers/metrics/swings. Reviewers should not expect live R50 data in Phase 1. Real wiring to `/api/*` + `/events` is Phase 2.
- **Preserved data layer is dead code for now:** `api.ts`, `useEvents.js`, `useCapture.js` compile/lint but are unreferenced. That is deliberate — do not delete them to "clean up unused" lint warnings.
- **MP MCP is a hard dependency:** if `read_artifact_files` cannot be reached, the agent MUST stop and report rather than invent component markup. The 25 ported files are the substance of this plan.
- **`tsc` strictness vs ported code:** MP components are real TypeScript, but porting can surface unused-import or implicit-any issues. The tsconfig already disables unused-symbol errors; fix genuine type errors locally rather than weakening `strict`.
- **Tailwind token fidelity:** the dark+green look depends entirely on MP's `index.css` tokens + `tailwind.config.js` `theme.extend`. If colors render as default Tailwind, the most likely cause is a missing `theme.extend` merge (Task 4/6) or a `content` glob that doesn't include `src/**/*.tsx`.
- **`darkMode`:** if the UI renders light, ensure `index.html` has `class="dark"` (or MP sets the dark root some other way) and `tailwind.config.js` `darkMode` matches MP's expectation.
- **No router:** dropping `react-router-dom` is intentional (MP is tab-state based). If a future deep-link requirement appears, that's Phase 2+, not here.
```

