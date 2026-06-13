<div align="center">

# GarageTEC

### Your home golf bay, with a tour coach built in.

GarageTEC turns a two-camera hitting bay and a Garmin Approach R50 into a private
swing studio: every shot is captured, measured, benchmarked against tour pros, and
read back to you in plain English by an AI coach. No subscriptions, no cloud
lock-in, no laptop juggling. It runs as a single touch-friendly app on the bay
screen.

</div>

![The Swing screen: two-camera video with a pose-skeleton overlay, a position
scrubber, the AI Coach read, and ball, club, and body metrics graded against tour
pros.](screenshot1.png)

---

## What it does

- **Catches every shot automatically.** The R50 streams shot data over GSPro Open
  Connect, and that shot is what triggers the cameras: the rolling video buffer is
  flushed to a clip the instant you hit, so ball data and swing video always arrive
  together, already matched. Nothing to sync, nothing to label.
- **Sees your body, not just the ball.** Two camera angles run through pose
  estimation to measure shoulder tilt, hip turn, spine angle, sway, early
  extension, and more, in 2D and (with calibrated cameras) 3D.
- **Grades you against the tour.** Every metric is benchmarked: ball and club
  numbers against TrackMan tour averages, body mechanics against a GolfTEC tour-pro
  reference, each shown with a green / yellow / red stoplight so you know at a
  glance what is dialed in and what is leaking strokes.
- **Coaches you like a pro on the lesson tee.** An AI coach reads each swing, and
  each whole session, and tells you what is working and what slipped, in tour-caliber
  plain language. Every sentence is anchored to your real measured numbers; the
  model is gated so it can never invent a stat.
- **Remembers and trends everything.** Pin any past swing, scrub it frame by frame
  with the skeleton overlay, and watch any metric trend over a session, week, month,
  or year against its tour benchmark line.

---

## See your progress, not just your last shot

History plots any body or ball metric over time with the tour average drawn right
on the chart, so improvement (and backsliding) is obvious.

![The History screen: a Shoulder Tilt trend line with the tour-average benchmark,
above a Ball Speed vs Tour chart, switchable by metric, club, and timeframe.](screenshot2.png)

## Pick up right where a session left off

Sessions are listed newest-first with at-a-glance stats, how many swings landed in
tour range, longest carry, the clubs you hit, and a one-line AI takeaway of what
improved or slipped. One tap loads a whole session back into the swing viewer.

![The Sessions screen: a most-recent-first list of practice sessions, each card
showing swing count, tour-range score, longest carry, club mix, an AI session
takeaway, and a Load Session button.](screenshot3.png)

---

## The screens

| Screen | What it's for |
|---|---|
| **Swing** | Live capture and review in one place. Follow the latest shot or pin any past one, scrub the two-camera video with a pose-skeleton overlay, step through swing positions, and read the AI coach alongside ball, club, and body metrics graded vs tour. |
| **History** | Trend any metric over session / week / month / year against its tour-average benchmark line. Tap a point to read its value. |
| **Sessions** | Browse past sessions with at-a-glance stats and AI takeaways; load one back into the Swing screen. |
| **Players** | Manage who is hitting (height and handedness drive the analysis). |
| **Connect** | Camera calibration, R50 connection status, and settings. |

---

## How it works

```
Garmin R50  ──(GSPro Open Connect, TCP/JSON)──▶  capture supervisor
                                                      │  shot fires
                                  rolling camera buffer ▶ clip
                                                      │
                            pose estimation ▶ 2D / 3D swing metrics
                                                      │
        benchmarks (TrackMan ball avgs · GolfTEC body refs) ▶ stoplight zones
                                                      │
                        AI coach (grounded to measured numbers)
                                                      │
                         FastAPI + SQLite  ──▶  touch UI on the bay screen
```

## Tech stack

- **Backend:** Python, FastAPI, Uvicorn, SQLite, Server-Sent Events for live updates.
- **Vision:** OpenCV, MediaPipe and RTMPose (ONNX Runtime) for pose, NumPy, two-camera
  calibration for 3D.
- **Frontend:** React, TypeScript, Vite, Tailwind CSS, Recharts, Framer Motion.
- **AI coach:** Anthropic Claude, with a strict grounding/validation gate.
- **Shipping:** packaged as a standalone Windows desktop app (PyInstaller + pywebview /
  WebView2), so the bay runs one icon, no terminal, no browser.

## Scope

GarageTEC is a **local, single-bay, single-household** app. Data lives on the bay
machine in SQLite; video and metrics never leave the building (the AI coach is the
only feature that calls out, and only when you give it an API key). It is built for a
touchscreen at arm's length, not for phones or the cloud.

---

## Running it

**Packaged app:** launch `GarageTEC.exe`. It creates its data folder on first run,
starts the local server, and opens in its own window.

**From source (dev):**

```bash
# backend + UI (from the repo root)
cd web/frontend && npm install && npm run build && cd ../..
python -m uvicorn web.backend.app:app --port 8000
# then open http://127.0.0.1:8000/

# build the desktop app
pyinstaller garagetec.spec --noconfirm
```

Set `ANTHROPIC_API_KEY` (in a repo-root `.env`) to enable the AI coach.
