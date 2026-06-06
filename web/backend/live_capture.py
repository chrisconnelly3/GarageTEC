"""Live swing capture: rolling-buffer + auto-trigger supervisor.

Mirrors CalibrationSupervisor's thread-safe shape. A capture thread continuously
reads composite frames from a camera source into a time-bounded RollingFrameBuffer
(``_loop``). When the R50 reports a shot, ``on_shot`` schedules ``capture_now``
after a short post-shot delay (so the full swing is in the buffer); ``capture_now``
flushes the buffer to a temp .mp4 and runs the existing ``process_video`` pipeline
on it, which persists a Swing and (via the existing sync path) auto-pairs it to
the shot. One ``live_swing_captured`` event is published per persisted swing.

Degrades gracefully: with no source/buffer everything is a safe no-op and status
reports "none"/idle. The device is owned here; nothing else opens hardware.
"""
import os
import tempfile
import threading
import time
from typing import Callable, Optional

from store import db as dbmod
from vision import constants as C
from vision.frames import LiveCameraSource, DualCameraSource
from vision.live_buffer import RollingFrameBuffer
from vision.pipeline import process_video

# Defaults (all overridable via configure()/constructor).
DEFAULT_FPS = 30.0
DEFAULT_WINDOW_S = 4.0        # rolling window spanning a full swing + lead-in
DEFAULT_POST_SHOT_DELAY_S = 0.6  # let the follow-through land in the buffer


class LiveCaptureSupervisor:
    """Owns a camera source + rolling buffer inside the FastAPI app.

    ``capture_now`` is the thread-free testable core (flush -> process_video ->
    emit). ``on_shot`` is the auto-trigger entry point CaptureSupervisor calls.
    ``source_factory`` is injectable so tests pass a fake (no device opened).
    """

    def __init__(self, *, conn, bus,
                 fps: float = DEFAULT_FPS,
                 window_s: float = DEFAULT_WINDOW_S,
                 post_shot_delay_s: float = DEFAULT_POST_SHOT_DELAY_S,
                 source_factory: Optional[Callable] = None,
                 split: float = C.DEFAULT_SPLIT,
                 db_path: Optional[str] = None):
        self.conn = conn
        self._db_path = db_path  # explicit path; falls back to default_db_path()
        self.bus = bus
        self.fps = fps
        self.window_s = window_s
        self.post_shot_delay_s = post_shot_delay_s
        self.split = split
        self._source_factory = source_factory

        self._lock = threading.Lock()
        self._run = False
        self._thread = None
        self._source = None
        self._capturing = False
        self._last_error = None
        self._swing_count = 0
        self._device_left = 0
        self._device_right = None
        self._mono = False
        self._buffer = RollingFrameBuffer(fps=fps, window_s=window_s)

    # ---- configuration ----------------------------------------------------
    def configure(self, *, device_left: int = 0, device_right: Optional[int] = None,
                  mono: bool = False, fps: Optional[float] = None,
                  window_s: Optional[float] = None,
                  post_shot_delay_s: Optional[float] = None):
        """Set source params + buffer window WITHOUT opening a device. Resets the
        buffer so a fresh window is used for the next session."""
        self._device_left = device_left
        self._device_right = device_right
        self._mono = mono
        if fps is not None:
            self.fps = fps
        if window_s is not None:
            self.window_s = window_s
        if post_shot_delay_s is not None:
            self.post_shot_delay_s = post_shot_delay_s
        self._buffer = RollingFrameBuffer(fps=self.fps, window_s=self.window_s)

    def _make_source(self):
        if self._source_factory:
            return self._source_factory()
        if self._mono or self._device_right is None:
            return LiveCameraSource(device_index=self._device_left, split=self.split)
        return DualCameraSource(self._device_left, self._device_right,
                                split=self.split)

    # ---- start / stop -----------------------------------------------------
    def start(self, **configure_kwargs):
        if configure_kwargs:
            self.configure(**configure_kwargs)
        with self._lock:
            if self._run:
                return
            try:
                self._source = self._make_source()
            except Exception as e:
                # No camera connected (hardware not present yet): stay idle.
                self._source = None
                self._last_error = f"no source: {e}"
                self._publish_status()
                return
            self._buffer.clear()
            self._run = True
            self._capturing = True
            self._last_error = None
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        self._publish_status()

    def stop(self):
        with self._lock:
            self._run = False
            self._capturing = False
        if self._source is not None:
            try:
                self._source.close()
            except Exception:
                pass
            self._source = None
        self._publish_status()

    def _loop(self):
        clock = 0.0
        dt = 1.0 / (self.fps or 30.0)
        while self._run:
            src = self._source
            frame = src.read_composite() if src is not None else None
            if frame is None:
                time.sleep(0.01)
                continue
            clock += dt
            try:
                self._buffer.push(frame, time_s=clock)
            except Exception:
                pass

    # ---- auto-trigger -----------------------------------------------------
    def on_shot(self, *, player_id, session_id, shot_id=None):
        """Called by CaptureSupervisor when an R50 shot is persisted. Schedules a
        capture after post_shot_delay_s on a daemon thread so the swing's full
        follow-through is in the buffer. Safe no-op if player/session missing."""
        if player_id is None or session_id is None:
            return
        t = threading.Thread(
            target=self._delayed_capture,
            kwargs={"player_id": player_id, "session_id": session_id,
                    "shot_id": shot_id},
            daemon=True)
        t.start()

    def _delayed_capture(self, *, player_id, session_id, shot_id):
        if self.post_shot_delay_s:
            time.sleep(self.post_shot_delay_s)
        try:
            self.capture_now(player_id=player_id, session_id=session_id,
                             shot_id=shot_id)
        except Exception as e:
            self._last_error = str(e)
            self._publish_status()

    # ---- testable trigger core -------------------------------------------
    def capture_now(self, *, player_id, session_id, shot_id=None):
        """Flush the rolling buffer to a temp mp4, run process_video on it, emit a
        live_swing_captured event per persisted swing, then clean up the temp
        file. Returns the list of swing ids produced (empty on no-op/error).

        Opens a FRESH db connection for every call so it is safe to run from any
        daemon thread (SQLite forbids sharing a connection across threads when
        check_same_thread is True, which is the default for store.db.connect()).
        """
        if len(self._buffer) == 0:
            return []
        fd, path = tempfile.mkstemp(suffix=".mp4", prefix="live_swing_")
        os.close(fd)
        swing_ids = []
        # Per-capture connection: thread-safe, closed in finally.
        cap_conn = dbmod.connect(self._db_path)
        try:
            written = self._buffer.flush_to_video(path)
            if written is None:
                return []

            def _on_swing(result):
                sid = getattr(result, "swing_id", None)
                swing_ids.append(sid)
                self._swing_count += 1
                # Best-effort real coaching: only when an API key is present.
                # Uses the SAME per-capture connection (cap_conn) so we never
                # share a conn across threads. Any failure (no key installed,
                # API/network error, validation reject) must NEVER break capture
                # -- the swing is already persisted; coaching is additive.
                if sid is not None and os.environ.get("ANTHROPIC_API_KEY"):
                    self._coach_swing(cap_conn, sid)
                self.bus.publish("live_swing_captured", {
                    "swing_id": sid, "shot_id": shot_id,
                    "player_id": player_id, "session_id": session_id})

            process_video(cap_conn, path, player_id=player_id,
                          session_id=session_id, on_swing=_on_swing)
        except Exception as e:
            self._last_error = str(e)
            self._publish_status()
            return []
        finally:
            try:
                cap_conn.close()
            except Exception:
                pass
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
        return swing_ids

    # ---- coaching (best-effort, key-gated) --------------------------------
    def _coach_swing(self, conn, swing_id):
        """Generate + persist grounded AI coaching for a freshly captured swing.

        Strictly best-effort: the swing is already persisted before this runs,
        so a missing/invalid ANTHROPIC_API_KEY, a network/API failure, or a
        validation rejection must never propagate. Errors are logged to
        ``_last_error`` (surfaced via status) and swallowed. Imports are local
        so the optional `anthropic` dependency is only touched when a key is set.
        """
        try:
            from coach.backend import make_backend
            from coach.coach import coach_swing
            backend = make_backend("cloud")
            coach_swing(conn, backend, swing_id)
        except Exception as e:
            self._last_error = f"coaching skipped: {e}"
            self._publish_status()

    # ---- status -----------------------------------------------------------
    def _source_kind(self):
        if self._source is None:
            return "none"
        if self._mono or self._device_right is None:
            return "single"
        return "dual"

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._run,
                "capturing": self._capturing,
                "source": self._source_kind(),
                "buffered_frames": len(self._buffer),
                "swing_count": self._swing_count,
                "fps": self.fps,
                "window_s": self.window_s,
                "post_shot_delay_s": self.post_shot_delay_s,
                "last_error": self._last_error,
            }

    def _publish_status(self):
        self.bus.publish("live_capture_status", self.status())
