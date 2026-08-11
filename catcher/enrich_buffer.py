"""Correlate OpenConnect wire shots with OpenFlight enrichment records.

Both channels are driven by the same physical shot microseconds apart, and both
round ball speed to one decimal, so ball speed is a strong, cheap key. Records
older than `window_s` are dropped, and each record is claimed at most once.

Thread-safe: the Socket.IO client thread adds records while the capture thread
takes them.
"""
import threading
import time
from typing import Callable, Optional

DEFAULT_WINDOW_S = 5.0
# Both sides round to 1dp; this only absorbs float representation noise.
SPEED_TOLERANCE = 0.06


class EnrichBuffer:
    def __init__(self, *, now: Callable[[], float] = time.monotonic,
                 window_s: float = DEFAULT_WINDOW_S):
        self._now = now
        self._window_s = window_s
        self._records = []            # list of (received_at, speed, record)
        self._lock = threading.Lock()

    def add_enrichment(self, record: dict) -> None:
        """Buffer an enrichment record. Records without a usable ball speed are
        dropped: without the key there is nothing to correlate on."""
        speed = record.get("ball_speed_mph")
        try:
            speed = float(speed)
        except (TypeError, ValueError):
            return
        with self._lock:
            self._prune_locked()
            self._records.append((self._now(), speed, record))

    def take_for(self, ball_speed) -> Optional[dict]:
        """Claim the oldest unexpired record matching `ball_speed`, or None."""
        try:
            target = float(ball_speed)
        except (TypeError, ValueError):
            return None
        with self._lock:
            self._prune_locked()
            for i, (_ts, speed, record) in enumerate(self._records):
                if abs(speed - target) <= SPEED_TOLERANCE:
                    del self._records[i]
                    return record
        return None

    def _prune_locked(self):
        cutoff = self._now() - self._window_s
        self._records = [r for r in self._records if r[0] >= cutoff]
