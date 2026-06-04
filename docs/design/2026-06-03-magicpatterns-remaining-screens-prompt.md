# MagicPatterns follow-up prompt — remaining 5 screens

**How to use:** Paste this as a NEW prompt **inside the SAME MagicPatterns design**
(https://www.magicpatterns.com/c/vbsfbzbwztgl3x464k7fdi) so it reuses the components already
built (Sidebar, Topbar, Card, MetricCard, AIInsightCard, etc.). Keep **Gemini 3.1** selected.
One prompt = one generation (token-efficient). If any single screen comes out thin, refine just
that one in a short follow-up.

---

## Prompt

Stay in the EXACT same dark + green design system and REUSE the existing components and tokens (Sidebar, Topbar, Card, Button, Badge, Tabs, Slider, Progress, MetricCard, AIInsightCard, Avatar, the garage-green #84CE39 + glow shadows, Inter/JetBrains-Mono, 18px radii). Add the remaining 5 screens, each reachable from the existing left sidebar (which already has Live and Review). Dark-mode only, touch-first (every target >=44px), futuristic-but-clean with subtle green glow. Use realistic golf data. Keep them visually consistent with the Live and Review screens already in this design.

1) HISTORY — header "History" with filter chips (Player, Club, Metric) and a segmented pill timeframe toggle (Session / Week / Month / Year). HERO: a large green-glow line chart of the selected body metric across recent sessions, with a floating tooltip callout bubble at the latest point (like a premium analytics dashboard). Below the chart: a horizontal row of small "metric trend" cards — each with a metric name, current value, a mini green sparkline, a delta vs baseline (green up / red down), and a small star badge when it's a personal best.

2) SESSIONS — header "Sessions". A vertical list of session cards, newest first. Each card: date + time, player avatar + name, club(s) hit, swing count, a one-line AI session summary, and 2-3 key stat chips (e.g. "Avg Hip Sway 2.1in", "Best swing"). If a session is currently live, pin it at the top with a green "● Recording" badge. Cards show a clear tappable "View swings" affordance.

3) PLAYERS — header "Players" with a primary "Add Player" pill button top-right. A responsive grid of player profile cards: large avatar/initials, name, height, an R/L handedness badge, total swings + sessions, and "last active" time. The currently-active player's card has a green ring + an "Active" badge. Include an "Add Player" modal/card with touch-sized fields: Name, Height (ft + in), Handedness (R/L pill toggle).

4) SYNC — header "Sync — match swings to shots" with a summary line ("12 auto-matched · 2 need review"). A list of match rows: each row pairs a camera SWING (small video thumbnail + timestamp + a couple of body-metric chips) with its proposed R50 SHOT (ball speed / carry / club path mini-chips) via a center connector that shows a confidence % (green pill if >=75%, amber if lower). Each row has Confirm (green), Re-assign, and Unlink pill buttons. A swing or shot with no partner appears as a single card flagged "needs a match".

5) CONNECT — header "Connect your R50". A friendly, reassuring 3-step wizard as big numbered step cards: Step 1 "On the R50: tap Connect, then GSPro", Step 2 "Join the R50's Wi-Fi (name + password shown on its screen)", Step 3 "Take a swing — shots appear automatically". A large central status indicator that goes from amber pulsing "Waiting for R50..." to green glowing "Connected" with the device name. Below, a compact Settings card with touch-sized controls: idle-timeout (minutes), units (yards / meters), and an advanced "port" field (default 921).
