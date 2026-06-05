"""Reliable shot persistence: save immediately, buffer on failure, replay later.

save(conn, shot) tries store.repo.save_shot. On any exception (e.g. DB locked)
the shot is appended as one JSON line to data/pending_shots.jsonl so nothing is
lost; save returns None to signal "buffered, not yet in the store". A periodic
replay(conn) re-saves every buffered shot into the store and, on full success,
clears the buffer. The buffer is human-readable JSONL keyed by Shot fields.
"""
import json
import os
import threading
from typing import List, Optional

from store import repo
from store.models import Shot

# Fields persisted to the buffer (everything that defines a Shot except its id).
_BUFFER_FIELDS = [
    "captured_at", "player_id", "session_id", "device_id", "shot_number",
    "ball_speed", "total_spin", "spin_axis", "hla", "vla", "carry",
    "club_speed", "attack_angle", "club_path", "face_to_target", "club",
    "raw_json",
]


def _default_buffer_path():
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(os.path.dirname(here), "data")
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "pending_shots.jsonl")


def _shot_to_record(shot: Shot) -> dict:
    return {f: getattr(shot, f) for f in _BUFFER_FIELDS}


def _record_to_shot(rec: dict) -> Shot:
    return Shot(**{f: rec.get(f) for f in _BUFFER_FIELDS})


class ShotPersister:
    def __init__(self, buffer_path: Optional[str] = None):
        self.buffer_path = buffer_path or _default_buffer_path()
        self._lock = threading.Lock()

    # ---- main path --------------------------------------------------------
    def save(self, conn, shot: Shot) -> Optional[Shot]:
        """Persist shot. On success return the saved Shot (with id). On store
        failure buffer it to disk and return None (never raises for DB errors)."""
        try:
            return repo.save_shot(conn, shot)
        except Exception:
            self._buffer(shot)
            return None

    def _buffer(self, shot: Shot):
        with self._lock:
            with open(self.buffer_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(_shot_to_record(shot)) + "\n")

    # ---- recovery ---------------------------------------------------------
    def pending_count(self) -> int:
        return len(self._read_buffer())

    def _read_buffer(self) -> List[dict]:
        if not os.path.exists(self.buffer_path):
            return []
        with self._lock:
            with open(self.buffer_path, encoding="utf-8") as fh:
                return [json.loads(line) for line in fh if line.strip()]

    def replay(self, conn) -> int:
        """Re-save every buffered shot into the store. On full success clear the
        buffer and return the count replayed; if a save fails mid-replay the
        already-saved records are dropped and the rest are rewritten to disk."""
        records = self._read_buffer()
        if not records:
            return 0
        replayed = 0
        for rec in records:
            try:
                repo.save_shot(conn, _record_to_shot(rec))
                replayed += 1
            except Exception:
                # store still down: keep the UNREPLAYED tail buffered, stop here
                remaining = records[replayed:]
                with self._lock:
                    with open(self.buffer_path, "w", encoding="utf-8") as fh:
                        for r in remaining:
                            fh.write(json.dumps(r) + "\n")
                return replayed
        # all replayed: clear the buffer
        with self._lock:
            if os.path.exists(self.buffer_path):
                os.remove(self.buffer_path)
        return replayed
