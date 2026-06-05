# GarageTEC — Hardware Shopping List

**Created:** 2026-06-04. A buy-list to stand up the full GarageTEC bay (DIY
GolfTEC-style 2-camera body capture + R50 launch data + the touch app). Grouped
by need, with the **hard specs that actually matter** called out. Prices are
rough US ballparks.

> You already have: the **Garmin R50** launch monitor (the app ingests it via
> GSPro Open Connect on TCP 921) and a **printed checkerboard** for calibration.

---

## 1. The two cameras (the heart of it)

You're planning **120fps**, which is a great call — it roughly halves the
worst-case timing skew between two free-running USB cameras vs 60fps, so your
instinct that higher fps mitigates desync is correct (max skew ≈ half a frame =
~4ms at 120fps). Buy **two identical units.**

**Hard specs to match on:**
| Spec | Target | Why |
|---|---|---|
| **Frame rate** | **≥120 fps** | freezes the swing; minimizes 2-cam desync |
| **Resolution at that fps** | **1080p preferred, 720p min** | pose accuracy; note USB bandwidth (below) |
| **Two IDENTICAL units** | same model/lens/firmware | clean software compositing + matched timing |
| **UVC compliant (USB Video Class)** | yes | so Windows/OpenCV see them with no special driver (the app enumerates UVC devices) |
| **MJPEG output OR USB 3.0** | yes | 1080p120 **uncompressed exceeds USB 2.0** bandwidth — you need MJPEG-compressed output or a USB-3 camera |
| **Manual / lockable focus + exposure + white balance** | yes | auto-focus/exposure "hunting" ruins consistency and calibration; lock them |
| **Lens FOV** | ~75–90° (fits a full swing from ~8–10 ft) | frame the whole body + club arc |
| **Shutter** | global shutter = nice-to-have | rolling shutter is fine for body rotations; global shutter helps club-level sharpness (but $$$) |
| Cable | **wired USB**, ideally detachable | length/extension flexibility |

**Where to look:** machine-vision USB cameras (ELP, Arducam, Innomaker) commonly
hit 720p120 / 1080p60–120 MJPEG with manual lenses for ~$40–90 each — the sweet
spot here. Consumer webcams (Logitech Brio etc.) are easy/UVC but most cap at
1080p60. True global-shutter USB3 cams (FLIR/Basler/e-con) are best-in-class but
$200–500+ each — overkill unless you chase club precision later.
**Budget: ~$80–180 for the pair** (mid-range), more for global shutter.

## 2. Mounting (keep them rock-steady)

Calibration is invalidated the instant a camera moves, so **stability > convenience.**
- **2× heavy/sturdy tripods** with a 1/4"-20 head, OR (better) **wall/ceiling
  mounts** — fixed mounts get bumped far less than tripods and keep your
  calibration valid for months. (~$25–60 each tripod; ~$15–30 each wall mount.)
- If tripods: **sandbags / weights** to anchor them.
- Positions: **face-on** camera perpendicular to the target line at ~chest
  height; **down-the-line** camera behind the player, on the target line, ~hip/
  chest height. Both need a clear, unobstructed view of the whole swing.

## 3. USB / connectivity

- **2× active (powered/repeater) USB extension cables** — passive USB maxes out
  ~5 m (USB2) / ~3 m (USB3). For runs to the mini-PC use **active extensions** or
  **USB-over-Cat6 extenders** for long runs. (~$15–35 each.)
- **1× powered USB 3.0 hub** — two MJPEG 1080p120 streams can exceed one port's
  bandwidth/power; a powered hub helps. **Better: plug each camera into a
  separate USB controller/bus** on the PC if you can (two streams on one
  controller can drop frames).
- Cable ties / raceway for cable management.

## 4. The mini-PC (runs the app + pose)

The AI coach is **cloud (Claude API)** by design, so **no GPU is required.** The
load is two camera streams + MediaPipe pose (CPU) + the FastAPI/React app. Recommend
**Windows** (the app uses Windows camera enumeration / DirectShow and is built/
tested on Windows).

**Minimum / recommended:**
| Part | Minimum | Recommended |
|---|---|---|
| CPU | modern 6-core (Intel i5 12th-gen+ / Ryzen 5 5600+) | 8-core i7 / Ryzen 7 (real-time 2-cam pose is CPU-heavy) |
| RAM | 16 GB | 32 GB |
| Storage | 500 GB NVMe SSD | 1 TB NVMe (swing videos are large) |
| USB | 2+ USB-3 ports on separate controllers | 4× USB-3 (cameras + touchscreen + R50 dongle) |
| GPU | none (integrated fine) | none — unless you later move the LLM local (then NVIDIA ≥8 GB VRAM, RTX 4060+) |
| OS | Windows 11 | Windows 11 |

**Where to look:** Beelink / Minisforum / GEEKOM Ryzen 7 mini-PCs (~$350–600), or
an Intel NUC. (A Mac mini M-series has a great CPU but the app's DirectShow camera
path is Windows-specific — stick with Windows.)

## 5. The display

- **1× touchscreen monitor, 24–27", 1080p+ , 10-pt capacitive multi-touch, USB
  touch (HID, plug-and-play).** The app is touch-first at standing height by the
  hitting area. (Dell/ViewSonic/Planar touch monitors, ~$250–500.) Bonus if it has
  an anti-glare matte finish and a sturdy stand or VESA mount.

## 6. Lighting (don't skip — it makes or breaks pose)

Clean, bright, **flicker-free** light = reliable body tracking (early testing
showed dark/uneven light hurts pose).
- **2–4× high-CRI (>90) flicker-free LED panels.** **Critical at 120fps:** cheap
  LED/fluorescent lights flicker at the AC line frequency and cause **banding /
  exposure pulsing** in 120fps footage — buy **flicker-free / high-frequency
  (DC-driven) LED panels** specifically. (~$40–100 each.)
- Aim for even, shadow-light from the front/sides; avoid a single harsh
  spotlight (glare on the board ruins calibration too).

## 7. The hitting area (if not already set up)

- **Golf hitting net or enclosure** + **side netting** (safety).
- **Hitting mat** (stance + strip).
- Optional simulator side (separate from GarageTEC analysis): **short-throw
  projector + impact screen** — the app design assumes the projector shows the
  GSPro/Garmin ball flight while the touchscreen shows GarageTEC. Only if you want
  the full sim visuals.

## 8. Networking & power

- Ensure the **R50 and the mini-PC are on the same LAN/Wi-Fi** so Open Connect
  (TCP 921) reaches the app. A small **Wi-Fi router or switch** if the garage has
  no coverage.
- **Surge-protected power strips / extension cords** for cameras (if powered),
  PC, monitor, lights.

## 9. Calibration consumables (mostly covered)

- **Rigid checkerboard** (you have the printout — mount it **flat** on foam-board/
  acrylic; see `docs/guides/bay-camera-calibration-guide.md`).
- A **ruler** to measure the printed square (only needed for absolute scale; the
  angle metrics are scale-invariant).

---

## Quick "core build" summary (minimum to be functional)

1. **2× identical UVC USB cameras**, ≥120fps, 1080p/720p, MJPEG, manual focus/
   exposure, ~80° lens.
2. **2× sturdy mounts** (wall mounts ideal) + anchoring.
3. **2× active USB extensions** + **1× powered USB-3 hub**.
4. **Windows mini-PC:** 8-core, 32 GB RAM, 1 TB NVMe, 4× USB-3, no GPU needed.
5. **24–27" capacitive touchscreen** + stand.
6. **Flicker-free high-CRI LED lighting.**
7. Net/mat (if needed) + same-LAN networking for the R50.

**Rough core total: ~$900–1,500** (excluding any net/mat/projector you already
have), driven mostly by the mini-PC + touchscreen. Cameras are the cheap part;
**spend your attention on matched cameras, fixed mounts, and flicker-free light** —
those three most affect data quality.
