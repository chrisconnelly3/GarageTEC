# Webcam smoke test (single-camera, validates the live plumbing)

A laptop webcam is ONE camera, so it can't produce a real stereo calibration —
but it exercises the whole live flow (device I/O, board detection, MJPEG preview,
coverage map, SSE). Square size doesn't matter here (angles are scale-invariant).

1. Start the app: `python -m web.backend.seed_dev` then
   `python -m uvicorn web.backend.app:app --port 8000`; open http://localhost:8000.
2. Go to **Connect → Camera Calibration**. Set Device to your webcam index
   (usually `0`), cols/rows to your board's inner corners, square to its inches.
3. Click **Start Capture**. Hold the printed checkerboard in front of the webcam.
4. CONFIRM: the live preview shows, the detected corners get drawn on the board,
   the good-pose counter climbs as you move the board to new areas, and the
   coverage grid fills in. (A single camera means "both halves" are the same
   webcam view — detection/preview/coverage all still exercise.)
5. With 8+ poses, **Run Calibration** returns a result (the numbers are
   meaningless with one camera — that's expected; this only validates plumbing).
6. Report what you saw (preview live? corners drawn? counter climbing? coverage
   filling? run returned?).
