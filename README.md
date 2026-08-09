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

## Build the bay: required hardware

Everything below is off-the-shelf. The parts that actually decide whether this works
well are **two identical cameras, mounts that never move, and flicker-free light** —
spend your attention there, not on the PC.

| Part | Qty | What we use | Notes |
|---|---|---|---|
| **Launch monitor** | 1 | **Garmin Approach R50** | The whole pipeline keys off it. Must reach the PC over your LAN, it streams shots via GSPro Open Connect (TCP 921). |
| **Cameras** | **2** | [ELP 2MP USB Camera Module, 1080p @ 120fps, OV4689, UVC](https://www.amazon.com/dp/B0BHWC6FVB) | Buy **two identical units**. 120fps halves the timing skew between two free-running cameras (~4 ms). UVC = no drivers. These are USB 2.0, so they rely on MJPEG for 1080p120. Lock focus/exposure/white balance; auto-hunting ruins calibration. |
| **Camera stands** | **2** | [Tonalee adjustable tripod, 24"–36", 360°](https://www.amazon.com/dp/B0FP4ZCS8Y) | **One per camera.** Face-on ≈ chest height, perpendicular to the target line; down-the-line behind the player, on the line. Anchor with sandbags. Wall/ceiling mounts are better if you can, calibration dies the moment a camera gets bumped. |
| **USB extensions** | 2 (optional) | [USB 3.0 extension, 20 ft](https://www.amazon.com/dp/B081H5L66K) | Only if the PC isn't next to the tripods. This one is *passive* and 20 ft is past spec for a USB 2.0 camera, if you get dropouts or no-signal, switch to an **active/repeater** extension. |
| **Touchscreen** | 1 | [Pisichen 27" 2K IPS, 10-point touch](https://www.amazon.com/dp/B0GJSHQNKL) | The UI is touch-first at standing height. A normal non-touch monitor works fine, you'd just be less cool. |
| **Controller PC** | 1 | Windows 11 mini-PC | Specs below. |
| **Lighting** | 2–4 | High-CRI (>90) **flicker-free** LED panels | Don't skip this. Cheap LEDs pulse at line frequency and put banding in 120fps footage, which wrecks pose tracking. Even, shadow-free front/side light. |
| **Calibration target** | 1 | Printed checkerboard on foam board | Needed for the 3D metrics. Must be **rigid and flat**. See the [calibration guide](docs/guides/bay-camera-calibration-guide.md). |
| **Hitting area** | — | Net or enclosure, mat, side netting | If you don't already have a bay. |
| **Powered USB hub** | 1 (optional) | Any powered USB 3.0 hub | Two 1080p120 MJPEG streams can starve one port. Better still: plug each camera into a **separate USB controller**. |

### Controller PC: minimum viable specs

Pose runs on a short recorded clip a second or two after you hit, not on a live
120fps stream, so this is laptop-class work, not a workstation.

| | Minimum | Comfortable |
|---|---|---|
| CPU | 4-core (i3-12xxx / Ryzen 3) | 6-core (i5 / Ryzen 5) |
| RAM | 8 GB | 16 GB |
| Storage | 256 GB NVMe | 500 GB NVMe |
| USB | 2× USB 3.0 | 4× USB 3.0, separate controllers |
| OS | Windows 11 | Windows 11 |
| **GPU** | **NVIDIA GTX 1050 Ti (4 GB)** | **GTX 1060 (6 GB) or better** |

**Yes, you need the graphics card.** GarageTEC uses a pose model called **RTMPose**
to find your body in the video, because the lighter CPU-only model (MediaPipe) loses
track of your arms exactly where it matters most: the backswing and the top, where
your hands overlap. RTMPose on a CPU runs at about 12 fps, which means **you'd stand
there waiting 10–15 seconds after every shot** before your replay could show the
skeleton overlay. That's not a golf lesson, that's a loading screen. Any cheap NVIDIA
card takes it to hundreds of fps, so the overlay is simply *there* the moment you turn
around. RTMPose only needs 1–2 GB of VRAM, so a used GTX 1050 Ti or 1060 (~$70–120) is
genuinely enough. Buy the GPU.

Budget for the core build lands around **$1,000–1,600**, mostly the PC and the
touchscreen. The cameras are the cheap part.

### One non-hardware requirement

An **Anthropic API key** for the AI coach. Everything else, capture, metrics,
benchmarks, trends, runs fully offline without it.

---

## Setup: from boxes to first swing

Plan on an afternoon. You do steps 1–5 once, ever.

### 1. Place the two cameras

Camera position is the single biggest lever on data quality, so take your time here.

- **Face-on camera:** directly in front of the golfer, **perpendicular to the target
  line**, at about **chest height**, roughly **8–10 ft** away.
- **Down-the-line camera:** **behind** the golfer, **on the target line** (looking
  where the ball is going), also chest height, 8–10 ft back.
- Both must see the **whole body plus the full club arc**, head to clubhead, top of
  the backswing included. Take a test video and check nothing clips out of frame.
- **Anchor everything.** Sandbag the tripod legs, tape the feet to the floor. Wall or
  ceiling mounts are better than tripods if you can manage it, because the single
  fastest way to break this system is bumping a camera.

### 2. Lock the camera settings

In your camera utility, turn **off** autofocus, auto-exposure, and auto white
balance, then lock each one manually. Cameras that keep re-focusing and
re-exposing mid-swing produce inconsistent data and invalidate calibration.

### 3. Sort out the lighting

Turn on your flicker-free LED panels and aim for **even, shadow-free light** from the
front and sides. Record a quick 120fps clip and look for dark rolling bands across
it. Bands mean a light is pulsing at the AC line frequency — that light has to be
replaced with a flicker-free (DC-driven) one. Pose tracking will not be reliable
until the bands are gone.

### 4. Plug in and install

1. Connect both cameras to the PC (separate USB ports, ideally separate controllers).
2. Connect the touchscreen.
3. Put the R50 and the PC **on the same network** so shot data can reach the app.
4. Launch `GarageTEC.exe`. It sets up its own data folder on first run.
5. Optional: to enable the AI coach, create a file named `.env` next to the app
   containing `ANTHROPIC_API_KEY=your-key-here`.

### 5. Calibrate the cameras (the important one)

**Skip this and your 3D numbers will be wrong.** Not slightly wrong, physically
impossible: an uncalibrated test produced a 175° spine tilt and 17 inches of sway.

**What calibration actually is, in plain English:** the software needs to know each
lens's quirks and exactly where the two cameras sit relative to each other. You can't
type that in, you measure it, by showing both cameras a printed checkerboard from lots
of angles and letting the software work backwards from how the pattern looks. That's
the whole idea: you're showing the cameras a ruler so they can work out their own
geometry.

**What you need:** a checkerboard printed at **100% scale / "Actual size"** (turn off
"fit to page"), glued **flat** to foam board, plus a ruler. The standard board is 10×7
squares, which the software counts as **9×6 inner corners**. **Measure one square with
your ruler in millimeters** and write the number down. Your printer is not exact, and
this measurement is what makes the numbers metrically correct.

**Then, in the app:**

> **Connect → Camera Calibration → Start Capture**

Stand in the hitting area and slowly wave the board around: near and far, left and
right, high and low, tilted every direction. Hold each pose about a second so it isn't
blurry, and keep the **whole board visible to both cameras** at once. Watch the
coverage map on screen fill in. After 20–40 good poses, press **Run Calibration**. It
saves and activates automatically.

**Check it worked:** hit a good swing and look at the top of your backswing. Shoulder
turn should read roughly **85–90°** and hip turn **45–50°**. Wildly different numbers
(10°, or 200°) mean something's off, see the
[full calibration guide](docs/guides/bay-camera-calibration-guide.md) for troubleshooting.

> ⚠️ **Recalibrate any time a camera moves or gets bumped.** Calibration is a
> measurement of where the cameras are. Move one, and the measurement is a lie.

### 6. Hit a shot

Pick who's hitting and the club in the top bar, press **Start Session**, and swing.
The R50 detects the shot, which triggers the cameras, and a few seconds later your
swing is on screen with the skeleton overlay, your numbers graded against tour pros,
and the coach's read.

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
