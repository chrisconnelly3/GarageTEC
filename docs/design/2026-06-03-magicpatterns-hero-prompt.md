# MagicPatterns prompt — GarageTEC hero screens (Live + Swing Review)

**How to use:** In MagicPatterns, select the **Gemini 3.1** model, **attach the 4 inspiration
screenshots** + the transparent logo (`web/frontend/public/garagetec-logo.png`), set design
system to **shadcn/ui**, and paste the prompt below.

**Locked decisions baked in:** dark-mode only · primary green sampled from the GarageTEC logo
**#84CE39** (deeper **#78BA30**) · touch-first · Tailwind + shadcn · the Live content hierarchy
(replay + body metrics + AI over a compact ball/club strip).

---

## Prompt

You are designing a **dark-mode-only** web dashboard for **GarageTEC**, a DIY at-home golf
swing-analysis and coaching tool — a GolfTEC-style coaching studio in your garage. It captures a
golfer's swing on camera + Garmin R50 launch-monitor data and shows body-mechanics metrics, AI
coaching, and swing replay. The user operates it on a **touchscreen monitor** at their hitting bay,
between shots.

Vibe: a **professional coaching instrument** that feels **futuristic and slightly gamified** —
confident, precise, premium. Glowing data, subtle glass/3D accents, badges and progress rings — but
never cluttered or toy-like. Match the dark + green-glow + component style of the attached reference
images (pill toggles, rounded icon nav, glowing charts, AI-insight cards with small colored icon
chips, glassy premium panels).

Stack: React + TypeScript + Tailwind CSS + shadcn/ui. **Dark mode only.**

Design tokens:
- Background: near-black, faint green tint `#0A0D0B`. Cards `#12171410`→`#121714`, elevated `#1A211D`. Hairline borders `#242C27`.
- PRIMARY = GarageTEC green `#84CE39` (deeper `#78BA30`). Use for active nav, primary pill buttons, positive deltas, success checks, and signature **glowing line/area charts** (soft glow `0 0 24px rgba(132,206,57,.35)`).
- Accent icon chips (categorize AI insights): blue `#3B82F6`, amber `#F59E0B`, magenta `#EC4899`. Negative/warning: red `#FF5A5A`.
- Text: off-white `#E7EEE9`; muted `#8B978F`; tiny UPPERCASE letter-spaced micro-labels.
- Type: Inter (or geometric sans); big bold **tabular** numbers for hero stats.
- Radii: cards 18px, pills fully rounded, buttons/inputs 12px. Soft shadows + subtle green glow on key elements; optional glassy translucent hero panels.
- Logo: GarageTEC wordmark (white "Garage" + green "TEC" with a swoosh) at top of the sidebar (transparent PNG attached).

Touch-first: every target ≥44px; pill toggles and large tappable cards; no hover-only menus; generous spacing.

Global layout (on every screen):
- **Left sidebar** (dark, icons + labels; active item = green pill with subtle glow): Live, Review, History, Sessions, Players, Sync; pinned at bottom: Connect/Settings. GarageTEC logo at top.
- **Persistent top bar:** left = a **"Who's hitting" player switcher** (avatar chips; active player has a green ring). Right = a **R50 status chip** (green dot "Connected" / amber "Waiting for R50" / "Paused") and a **Pause/Resume** pill toggle.

SCREEN 1 — **Live** (default/home; during-practice). Priority, largest→smallest:
1. **Swing Replay (HERO, largest):** video player of the latest swing with a pose **skeleton overlay**, a **Realtime ⇄ Slow-mo** pill toggle, a scrub bar + frame-step, subtle green-glow frame. (Placeholder golfer silhouette + skeleton.)
2. **Body-Movement Metrics (primary):** a grid of ~6 metric cards. Each: small uppercase name (Shoulder Tilt, Hip Sway, Spine Angle, Early Extension, Hand Depth, Shoulder Turn), big value + unit (e.g. `38°`, `2.5 in`), a delta vs the player's baseline (green ▲ / red ▼), and a thin "vs ideal" range bar or mini sparkline. Mark estimated metrics with a small `≈ est.` badge.
3. **AI Read (primary):** an "AI Insights"-style card — a headline (e.g. "Hips slid 2.5 in toward target at impact"), 2–3 findings each with a small colored icon chip + the cited metric + a one-line drill, and a green check / severity dot.
4. **Ball & Club strip (secondary, compact, de-emphasized):** a slim horizontal row of small muted stat chips — Ball Speed, Spin, Launch, Carry, Club Speed, Path, Face, AoA. Visually minor (this is already shown on the golfer's main projector).
- Empty/waiting state: a calm "Waiting for your R50… take a swing" with the green status pulsing.
- A celebratory "✓ Shot captured" moment when a swing lands (metrics glow in).

SCREEN 2 — **Swing Review** (deep-dive one swing). Same sidebar + top bar.
- **HERO:** large video scrubber with skeleton overlay, and an **8-phase timeline** beneath as a horizontal track with labeled markers — Address, Takeaway, Lead-arm parallel, Top, Transition, Shaft parallel, Impact, Follow-through — tap a phase to jump; active marker is green.
- **Full metric panel:** every body metric at Address / Top / Impact (columns), each vs baseline and vs ideal, with confidence flags.
- **AI feedback panel:** fuller — headline, findings list, recommended drills.
- **Matched shot panel (compact):** the R50 ball + club numbers for this swing.
- Optional: a small green-glow trend sparkline per metric.

Use realistic golf values. Deliver both screens as responsive React + Tailwind + shadcn components, desktop touchscreen first, phone-responsive.
