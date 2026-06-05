# Webcam smoke test (single-camera, validates the live plumbing)

A laptop webcam is ONE camera, so it can't produce a real stereo calibration —
but it exercises the whole live flow (device I/O, board detection, MJPEG preview,
coverage map, SSE). Square size doesn't matter here (angles are scale-invariant).

1. Start the app: `python -m web.backend.seed_dev` then
   `python -m uvicorn web.backend.app:app --port 8000`; open http://localhost:8000.
2. Go to **Connect → Camera Calibration**. Set Device to your webcam index
   (usually `0`), and set **Inner cols / Inner rows to YOUR board's inner-corner
   count** (a 10×7-square board = 9×6 inner corners; in general squares − 1 in
   each direction — this must match or detection fails). Square size in inches.
3. ✅ **CHECK the "Single-camera test mode" box.** This is REQUIRED for a webcam.
   (Without it the app splits the frame into two camera views and looks for the
   board in BOTH halves — one webcam shows one board straddling the split, so it's
   found in neither and nothing detects. Mono mode runs detection on the whole
   frame instead.)
4. Click **Start Capture**. Hold the printed checkerboard in front of the webcam,
   filling a good part of the frame, held still ~1s, moved to different positions.
5. CONFIRM: the live preview shows, **green detected corners get drawn on the
   board**, the good-pose counter climbs as you move the board to new areas, and
   the coverage grid fills in.
6. With 8+ poses, **Run Calibration** returns an *informational* message
   ("single-camera test mode: live capture + board detection validated; real
   calibration needs the two-camera bay") — that's expected; one camera can't
   produce a real stereo calibration.
7. Report what you saw (preview live? **green corners drawn?** counter climbing?
   coverage filling? run message?).

> If you set the wrong cols/rows, OR forget the Single-camera checkbox, you'll see
> the video preview but NO corners and a stuck 0 counter — exactly the two things
> to get right.
