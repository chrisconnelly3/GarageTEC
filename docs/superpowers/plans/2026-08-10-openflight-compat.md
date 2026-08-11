# OpenFlight Launch-Monitor Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let GarageTEC ingest shots from the open-source OpenFlight radar launch monitor, grading and coaching only the numbers OpenFlight actually measured.

**Architecture:** Two channels. OpenFlight's GSPro OpenConnect V1 socket (TCP 921) stays load-bearing — it carries the canonical shot and triggers camera capture, exactly as the R50 does. A second, additive channel subscribes to OpenFlight's Socket.IO `shot` event to recover per-field provenance (source, confidence, real nulls) that the GSPro wire format cannot express. A pure trust-policy module turns that provenance into three tiers (measured / estimated / absent) that drive stoplight grading, UI display, and what the AI coach may assert.

**Tech Stack:** Python 3.12, FastAPI, SQLite, pytest; `python-socketio[client]`; React + TypeScript + Vitest.

**Spec:** `docs/superpowers/specs/2026-08-10-openflight-compat-design.md`

---

## File Structure

| File | Responsibility |
|---|---|
| `catcher/trust.py` *(new)* | Pure per-field trust policy. Thresholds + device profiles. No I/O. |
| `catcher/openflight_enrich.py` *(new)* | Socket.IO client + payload normalization. Callback-driven, no DB. |
| `catcher/enrich_buffer.py` *(new)* | Pure correlation buffer pairing wire shots to enrichment records. |
| `catcher/shotmap.py` *(edit)* | Honor `ContainsClubData`; device-scoped zero handling. |
| `catcher/openconnect.py` *(edit)* | `send_player_update()` for mid-connection club pushes. |
| `store/schema.sql`, `store/db.py`, `store/models.py`, `store/repo.py` *(edit)* | `enrichment_json` column + migration + update function. |
| `web/backend/capture.py` *(edit)* | Address discovery, enrichment lifecycle, correlation wiring, club push. |
| `web/backend/api_swings.py` *(edit)* | Expose tiers to the frontend. |
| `coach/context.py`, `coach/prompt.py` *(edit)* | Tier-aware grounding. |
| `web/frontend/src/components/MetricCard.tsx` *(edit)* | `estimated` marker. |
| `web/frontend/src/lib/types.ts` *(edit)* | Tier types. |
| `garagetec.spec` *(edit)* | Bundle `socketio` client. |

---

## Task 1: Trust policy module

Pure, dependency-free foundation. Everything else consumes it.

**Files:**
- Create: `catcher/trust.py`
- Test: `catcher/tests/test_trust.py`

- [ ] **Step 1: Write the failing test**

Create `catcher/tests/test_trust.py`:

```python
from catcher import trust


# A full OpenFlight `shot` payload (the inner dict of the Socket.IO "shot" event),
# with every field measured and high-confidence.
FULL = {
    "ball_speed_mph": 148.2,
    "club_speed_mph": 102.1,
    "estimated_carry_yards": 232,
    "carry_range": [228, 236],
    "launch_angle_vertical": 13.8,
    "launch_angle_vertical_confidence": 0.92,
    "launch_angle_vertical_source": "iwr6843",
    "launch_angle_horizontal": 1.2,
    "launch_angle_horizontal_confidence": 0.88,
    "launch_angle_horizontal_source": "iwr6843",
    "spin_rpm": 2710,
    "spin_rpm_measured": 2710,
    "spin_confidence": 0.81,
    "spin_source": "rolling_buffer",
    "spin_axis_deg": -6.4,
    "club_path_deg": 2.1,
}


def test_all_measured_when_confident():
    t = trust.derive_tiers(FULL)
    assert t["ball_speed"] == trust.MEASURED
    assert t["club_speed"] == trust.MEASURED
    assert t["vla"] == trust.MEASURED
    assert t["hla"] == trust.MEASURED
    assert t["total_spin"] == trust.MEASURED
    assert t["spin_axis"] == trust.MEASURED
    assert t["carry"] == trust.MEASURED


def test_spin_without_measured_twin_is_estimated():
    """spin_rpm present but spin_rpm_measured None => the value is modelled."""
    payload = dict(FULL, spin_rpm=2500, spin_rpm_measured=None)
    t = trust.derive_tiers(payload)
    assert t["total_spin"] == trust.ESTIMATED
    assert t["back_spin"] == trust.ESTIMATED
    assert t["side_spin"] == trust.ESTIMATED


def test_low_confidence_is_estimated():
    payload = dict(FULL, launch_angle_vertical_confidence=0.4)
    assert trust.derive_tiers(payload)["vla"] == trust.ESTIMATED


def test_none_is_absent():
    payload = dict(FULL, club_speed_mph=None, spin_axis_deg=None)
    t = trust.derive_tiers(payload)
    assert t["club_speed"] == trust.ABSENT
    assert t["spin_axis"] == trust.ABSENT


def test_carry_inherits_launch_angle_tier():
    """Carry is always model-derived; it is only as good as the launch angle."""
    payload = dict(FULL, launch_angle_vertical_confidence=0.1)
    assert trust.derive_tiers(payload)["carry"] == trust.ESTIMATED


def test_club_path_always_estimated():
    """OpenFlight documents club path as experimental."""
    assert trust.derive_tiers(FULL)["club_path"] == trust.ESTIMATED


def test_fields_openflight_never_produces_are_absent():
    t = trust.derive_tiers(FULL)
    assert t["attack_angle"] == trust.ABSENT
    assert t["face_to_target"] == trust.ABSENT


def test_no_enrichment_falls_back_conservatively():
    t = trust.derive_tiers(None)
    assert t["ball_speed"] == trust.MEASURED
    assert t["carry"] == trust.MEASURED
    assert t["vla"] == trust.ESTIMATED
    assert t["total_spin"] == trust.ESTIMATED
    assert t["attack_angle"] == trust.ABSENT


def test_schema_drift_does_not_crash():
    """Unknown/renamed keys must degrade, never raise."""
    t = trust.derive_tiers({"ball_speed_mph": 100.0, "totally_new_key": 1})
    assert t["ball_speed"] == trust.MEASURED
    assert t["vla"] == trust.ABSENT


def test_profile_for_openflight_zeroes():
    p = trust.profile_for("OpenFlight")
    assert "hla" in p.zero_means_absent
    assert "attack_angle" in p.zero_means_absent


def test_unknown_device_gets_permissive_profile():
    """An R50 (or any future device) must not have its zeros nulled."""
    p = trust.profile_for("GARMIN-R50")
    assert p.zero_means_absent == frozenset()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest catcher/tests/test_trust.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'catcher.trust'`

- [ ] **Step 3: Write the implementation**

Create `catcher/trust.py`:

```python
"""Per-field trust policy for incoming launch-monitor shots.

Pure: no I/O, no DB, no network. Given an OpenFlight enrichment record (or None),
decide for each GarageTEC shot field whether the number was actually MEASURED,
is a model-derived ESTIMATE, or is ABSENT. Callers use the tier to decide whether
to grade a value against tour averages, badge it in the UI, or hide it.

Also owns the per-device profile that says which literal 0.0 values on the
OpenConnect wire mean "no measurement" (see `zero_means_absent`).
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

MEASURED = "measured"
ESTIMATED = "estimated"
ABSENT = "absent"

# Mirrors OpenFlight's own SPIN_CONFIDENCE_HIGH (src/openflight/launch_monitor.py:17),
# the bar it uses internally before accepting a spin reading. Tune here only.
CONFIDENCE_MIN = 0.7

# Substrings that mark a source as model-derived. Matching is defensive: an
# UNRECOGNIZED source never forces ESTIMATED on its own (confidence still decides),
# so a renamed source string upstream degrades gracefully instead of mislabeling.
ESTIMATE_SOURCE_MARKERS = ("model", "estimate", "fallback", "default")


@dataclass(frozen=True)
class DeviceProfile:
    """Per-device wire quirks.

    zero_means_absent: fields where a literal 0.0 on the OpenConnect wire means
    "no measurement" rather than a real zero. Only ever populated for devices
    that pad absent fields with 0.0. Empty for the R50 and anything unknown,
    because a measured HLA/spin-axis/attack-angle can legitimately BE zero.
    """
    zero_means_absent: frozenset = field(default_factory=frozenset)


# OpenFlight's GSPro codec always emits a ClubData block and defaults unset
# numeric fields to 0.0. AngleOfAttack and FaceToTarget are never assigned at
# all; HLA and SpinAxis are set to 0.0 by its resolver when unmeasured.
OPENFLIGHT_PROFILE = DeviceProfile(
    zero_means_absent=frozenset({"hla", "spin_axis", "attack_angle", "face_to_target"})
)
PERMISSIVE_PROFILE = DeviceProfile()

DEVICE_PROFILES: Dict[str, DeviceProfile] = {
    "OpenFlight": OPENFLIGHT_PROFILE,
}


def profile_for(device_id: Optional[str]) -> DeviceProfile:
    """Profile for a DeviceID. Unknown devices get the permissive profile."""
    return DEVICE_PROFILES.get(device_id or "", PERMISSIVE_PROFILE)


def _num(value):
    """Coerce to float, or None when missing/unparseable."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tier(value, *, source=None, confidence=None) -> str:
    if _num(value) is None:
        return ABSENT
    if source is not None:
        text = str(source).lower()
        if any(marker in text for marker in ESTIMATE_SOURCE_MARKERS):
            return ESTIMATED
    conf = _num(confidence)
    if conf is not None and conf < CONFIDENCE_MIN:
        return ESTIMATED
    return MEASURED


# Tiers used when no enrichment record arrived. Ball speed and carry are the
# monitor's load-bearing outputs and are always sent; anything OpenFlight may
# have substituted is treated as an estimate rather than graded as fact.
_NO_ENRICHMENT = {
    "ball_speed": MEASURED,
    "carry": MEASURED,
    "club_speed": MEASURED,
    "vla": ESTIMATED,
    "hla": ESTIMATED,
    "total_spin": ESTIMATED,
    "back_spin": ESTIMATED,
    "side_spin": ESTIMATED,
    "spin_axis": ESTIMATED,
    "club_path": ESTIMATED,
    "attack_angle": ABSENT,
    "face_to_target": ABSENT,
}


def derive_tiers(enrichment: Optional[dict]) -> Dict[str, str]:
    """Map each GarageTEC shot field to MEASURED / ESTIMATED / ABSENT.

    `enrichment` is the inner "shot" dict of OpenFlight's Socket.IO event, or
    None when no enrichment was correlated. Every lookup is defensive so a
    renamed or removed upstream key degrades one field instead of raising.
    """
    if not enrichment:
        return dict(_NO_ENRICHMENT)

    e = enrichment
    tiers: Dict[str, str] = {}

    tiers["ball_speed"] = _tier(e.get("ball_speed_mph"))
    tiers["club_speed"] = _tier(e.get("club_speed_mph"))
    tiers["spin_axis"] = _tier(e.get("spin_axis_deg"))

    tiers["vla"] = _tier(
        e.get("launch_angle_vertical"),
        source=e.get("launch_angle_vertical_source"),
        confidence=e.get("launch_angle_vertical_confidence"),
    )
    tiers["hla"] = _tier(
        e.get("launch_angle_horizontal"),
        source=e.get("launch_angle_horizontal_source"),
        confidence=e.get("launch_angle_horizontal_confidence"),
    )

    # Spin: OpenFlight exposes both the final value and the raw measurement.
    # A final value with no measured twin is the per-club model -> ESTIMATED.
    # This is a structural signal, so it survives source-string renames.
    spin_tier = _tier(
        e.get("spin_rpm"),
        source=e.get("spin_source"),
        confidence=e.get("spin_confidence"),
    )
    if spin_tier != ABSENT and _num(e.get("spin_rpm_measured")) is None:
        spin_tier = ESTIMATED
    tiers["total_spin"] = spin_tier
    # Back/side spin are trigonometric derivations of total spin and its axis.
    tiers["back_spin"] = spin_tier
    tiers["side_spin"] = spin_tier

    # Carry is never directly observed: it is a ballistic model output, so it is
    # only as trustworthy as the launch angle that drove it.
    tiers["carry"] = (
        ABSENT if _num(e.get("estimated_carry_yards")) is None else tiers["vla"]
    )

    # OpenFlight documents club path as experimental.
    tiers["club_path"] = (
        ABSENT if _num(e.get("club_path_deg")) is None else ESTIMATED
    )

    # Never produced by OpenFlight's GSPro codec.
    tiers["attack_angle"] = ABSENT
    tiers["face_to_target"] = ABSENT

    return tiers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest catcher/tests/test_trust.py -v`
Expected: PASS, 11 tests

- [ ] **Step 5: Commit**

```bash
git add catcher/trust.py catcher/tests/test_trust.py
git commit -m "feat(catcher): per-field trust policy for launch-monitor shots"
```

---

## Task 2: shotmap honors ContainsClubData and device zeros

Valuable on its own: it stops GarageTEC storing `0.0` as a real measurement from *any* OpenConnect device.

**Files:**
- Modify: `catcher/shotmap.py` (whole file rewritten below)
- Test: `catcher/tests/test_shotmap.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `catcher/tests/test_shotmap.py`:

```python
OPENFLIGHT_MSG = {
    "DeviceID": "OpenFlight",
    "Units": "Yards",
    "ShotNumber": 3,
    "APIversion": "1",
    "BallData": {
        "Speed": 121.4, "SpinAxis": 0.0, "TotalSpin": 7000.0,
        "BackSpin": 7000.0, "SideSpin": 0.0, "HLA": 0.0, "VLA": 16.3,
        "CarryDistance": 171.0,
    },
    # OpenFlight always sends the block, padding unset numbers with 0.0.
    "ClubData": {
        "Speed": 0.0, "AngleOfAttack": 0.0, "FaceToTarget": 0.0, "Path": 2.1,
    },
    "ShotDataOptions": {
        "ContainsBallData": True,
        "ContainsClubData": False,
        "LaunchMonitorIsReady": True,
        "LaunchMonitorBallDetected": True,
        "IsHeartBeat": False,
    },
}


def test_club_data_ignored_when_flag_false():
    shot = map_message(OPENFLIGHT_MSG)
    assert shot.club_speed is None
    assert shot.attack_angle is None
    assert shot.face_to_target is None
    assert shot.club_path is None


def test_openflight_zeros_become_none():
    shot = map_message(OPENFLIGHT_MSG)
    assert shot.hla is None
    assert shot.spin_axis is None
    # Real measurements are untouched.
    assert shot.ball_speed == 121.4
    assert shot.vla == 16.3
    assert shot.carry == 171.0


def test_r50_zeros_are_preserved():
    """Regression: a measured zero from a permissive device stays 0.0."""
    msg = json.loads(json.dumps(SHOT_MSG))
    msg["BallData"]["HLA"] = 0.0
    msg["BallData"]["SpinAxis"] = 0.0
    shot = map_message(msg)
    assert shot.hla == 0.0
    assert shot.spin_axis == 0.0


def test_r50_club_data_still_read():
    """Regression: the R50 sends no ContainsClubData flag; keep reading club data."""
    shot = map_message(SHOT_MSG)
    assert shot.club_speed == 102.1
    assert shot.attack_angle == -2.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest catcher/tests/test_shotmap.py -v`
Expected: FAIL — `test_club_data_ignored_when_flag_false` asserts `None` but gets `0.0`

- [ ] **Step 3: Write the implementation**

Replace the body of `catcher/shotmap.py` below the imports. Full file:

```python
"""Pure mapping from GSPro Open Connect JSON messages to store.models.Shot.

No I/O, no DB, no tkinter. Distinguishes shots from heartbeats. Stores whatever
ball/club fields arrive plus the full original message in raw_json; no field is
assumed mandatory (a monitor may send ball-only or include club data).

Two wire quirks are normalized here so the rest of the app never sees a fake
number:
  * ShotDataOptions.ContainsClubData == False -> the ClubData block is padding
    and is ignored wholesale.
  * Devices that pad absent numerics with 0.0 (see catcher.trust device
    profiles) have those specific zeros mapped to None. Permissive devices such
    as the R50 keep their zeros, because a measured angle can legitimately be 0.
"""
import json
from typing import Optional

from store import db as dbmod
from store.models import Shot
from catcher import trust


def is_heartbeat(obj: dict) -> bool:
    sdo = obj.get("ShotDataOptions") or {}
    return bool(sdo.get("IsHeartBeat"))


def _num(d: dict, key):
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def map_message(obj: dict) -> Optional[Shot]:
    """Return a Shot for a shot message, or None for a heartbeat.

    captured_at is stamped now (UTC ISO-8601); player_id / session_id are left
    None for the SessionManager to assign.
    """
    if is_heartbeat(obj):
        return None

    device_id = obj.get("DeviceID")
    profile = trust.profile_for(device_id)

    ball = obj.get("BallData") or {}
    sdo = obj.get("ShotDataOptions") or {}
    # Absent flag means "legacy device, trust the block" (the R50 sends no flag).
    club = obj.get("ClubData") or {}
    if sdo.get("ContainsClubData") is False:
        club = {}

    shot_number = obj.get("ShotNumber")
    if shot_number is not None:
        try:
            shot_number = int(shot_number)
        except (TypeError, ValueError):
            shot_number = None

    def field(value, name):
        """Null out a padded zero for devices known to pad that field."""
        if value == 0.0 and name in profile.zero_means_absent:
            return None
        return value

    return Shot(
        captured_at=dbmod.now_iso(),
        device_id=device_id,
        shot_number=shot_number,
        ball_speed=_num(ball, "Speed"),
        total_spin=_num(ball, "TotalSpin"),
        spin_axis=field(_num(ball, "SpinAxis"), "spin_axis"),
        hla=field(_num(ball, "HLA"), "hla"),
        vla=_num(ball, "VLA"),
        carry=_num(ball, "CarryDistance"),
        club_speed=_num(club, "Speed"),
        attack_angle=field(_num(club, "AngleOfAttack"), "attack_angle"),
        club_path=_num(club, "Path"),
        face_to_target=field(_num(club, "FaceToTarget"), "face_to_target"),
        raw_json=json.dumps(obj),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest catcher/tests/ -v`
Expected: PASS, all existing shotmap tests plus the 4 new ones

- [ ] **Step 5: Commit**

```bash
git add catcher/shotmap.py catcher/tests/test_shotmap.py
git commit -m "fix(catcher): honor ContainsClubData and device-padded zeros"
```

---

## Task 3: Persist enrichment records

**Files:**
- Modify: `store/schema.sql:38`, `store/db.py:48`, `store/models.py:59`, `store/repo.py:245`
- Test: `store/tests/test_shots.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `store/tests/test_shots.py`:

```python
def test_set_shot_enrichment_roundtrip(db):
    from store.models import Shot
    pid = repo.get_or_create_player(db, "E", 70.0, "R").id
    sid = repo.create_session(db, pid).id
    shot = repo.save_shot(db, Shot(captured_at="2026-08-10T00:00:00+00:00",
                                   player_id=pid, session_id=sid,
                                   ball_speed=120.0))
    assert shot.enrichment_json is None

    repo.set_shot_enrichment(db, shot.id, '{"ball_speed_mph": 120.0}')
    again = repo.get_shot(db, shot.id)
    assert again.enrichment_json == '{"ball_speed_mph": 120.0}'
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest store/tests/test_shots.py::test_set_shot_enrichment_roundtrip -v`
Expected: FAIL with `AttributeError: 'Shot' object has no attribute 'enrichment_json'`

- [ ] **Step 3: Write the implementation**

In `store/schema.sql`, change the `shot` table's last column line from:

```sql
  dedupe_key TEXT
);
```

to:

```sql
  dedupe_key TEXT,
  enrichment_json TEXT
);
```

In `store/db.py`, after the existing `dedupe_key` migration line, add:

```python
    _add_column_if_missing(conn, "shot", "enrichment_json", "TEXT")
```

In `store/models.py`, in the `Shot` dataclass after `dedupe_key`, add:

```python
    enrichment_json: Optional[str] = None
```

In `store/repo.py`, add `"enrichment_json"` to the end of `_SHOT_COLS`:

```python
_SHOT_COLS = [
    "swing_id", "player_id", "session_id", "captured_at", "device_id",
    "shot_number", "ball_speed", "total_spin", "spin_axis", "hla", "vla",
    "carry", "club_speed", "attack_angle", "club_path", "face_to_target",
    "club", "raw_json", "dedupe_key", "enrichment_json",
]
```

In `store/repo.py`, inside `_shot_from_row`, add the field to the constructed
`Shot(...)` call (after `club=r["club"]`):

```python
                enrichment_json=r["enrichment_json"],
```

In `store/repo.py`, after `link_shot_to_swing`, add:

```python
def set_shot_enrichment(conn, shot_id, enrichment_json: str):
    """Attach a launch-monitor enrichment record to an already-persisted shot."""
    conn.execute("UPDATE shot SET enrichment_json=? WHERE id=?",
                 (enrichment_json, shot_id))
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest store/tests/ -v`
Expected: PASS, all store tests including the new one

- [ ] **Step 5: Commit**

```bash
git add store/schema.sql store/db.py store/models.py store/repo.py store/tests/test_shots.py
git commit -m "feat(store): persist launch-monitor enrichment records on shots"
```

---

## Task 4: Correlation buffer

Pairs a wire shot with its enrichment record. Pure and time-injectable so tests need no sleeps.

**Files:**
- Create: `catcher/enrich_buffer.py`
- Test: `catcher/tests/test_enrich_buffer.py`

- [ ] **Step 1: Write the failing test**

Create `catcher/tests/test_enrich_buffer.py`:

```python
from catcher.enrich_buffer import EnrichBuffer


def test_enrichment_first_then_shot_matches():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.2) == {"ball_speed_mph": 148.2}


def test_match_is_claimed_only_once():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.2) is not None
    assert buf.take_for(148.2) is None


def test_speed_mismatch_does_not_match():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(150.0) is None


def test_stale_records_expire():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0], window_s=5.0)
    buf.add_enrichment({"ball_speed_mph": 148.2})
    clock[0] = 1006.0
    assert buf.take_for(148.2) is None


def test_duplicate_speeds_are_matched_first_in_first_out():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2, "n": 1})
    buf.add_enrichment({"ball_speed_mph": 148.2, "n": 2})
    assert buf.take_for(148.2)["n"] == 1
    assert buf.take_for(148.2)["n"] == 2


def test_rounding_tolerance():
    """Both channels round to 1dp, but tolerate float noise anyway."""
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.24) is not None


def test_missing_ball_speed_is_ignored():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"no_speed": True})
    assert buf.take_for(148.2) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest catcher/tests/test_enrich_buffer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'catcher.enrich_buffer'`

- [ ] **Step 3: Write the implementation**

Create `catcher/enrich_buffer.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest catcher/tests/test_enrich_buffer.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Commit**

```bash
git add catcher/enrich_buffer.py catcher/tests/test_enrich_buffer.py
git commit -m "feat(catcher): ball-speed correlation buffer for enrichment records"
```

---

## Task 5: Socket.IO enrichment client

**Files:**
- Create: `catcher/openflight_enrich.py`
- Test: `catcher/tests/test_openflight_enrich.py`
- Modify: `requirements-dev.txt`

- [ ] **Step 1: Add the dependency**

Append to `requirements-dev.txt`:

```
python-socketio[client]>=5.11
```

Run: `python -m pip install "python-socketio[client]>=5.11"`
Expected: installs successfully

- [ ] **Step 2: Write the failing test**

Create `catcher/tests/test_openflight_enrich.py`:

```python
from catcher.openflight_enrich import normalize_event, url_for_host


FULL_EVENT = {
    "shot": {
        "ball_speed_mph": 148.2,
        "club_speed_mph": 102.1,
        "estimated_carry_yards": 232,
        "launch_angle_vertical": 13.8,
        "launch_angle_vertical_confidence": 0.92,
        "spin_rpm": 2710,
        "spin_rpm_measured": 2710,
    },
    "stats": {"shot_count": 4},
}


def test_normalize_extracts_inner_shot():
    assert normalize_event(FULL_EVENT)["ball_speed_mph"] == 148.2


def test_normalize_accepts_bare_shot_dict():
    """Tolerate the payload arriving unwrapped."""
    assert normalize_event(FULL_EVENT["shot"])["ball_speed_mph"] == 148.2


def test_normalize_rejects_non_dict():
    assert normalize_event(None) is None
    assert normalize_event([1, 2, 3]) is None
    assert normalize_event("shot") is None


def test_normalize_rejects_shot_without_ball_speed():
    assert normalize_event({"shot": {"club_speed_mph": 90.0}}) is None


def test_schema_drift_keeps_what_it_can():
    """Renamed/removed keys must not crash; ball speed is the only requirement."""
    drifted = {"shot": {"ball_speed_mph": 100.0, "launch_angle_v2": 12.0}}
    out = normalize_event(drifted)
    assert out["ball_speed_mph"] == 100.0
    assert "launch_angle_v2" in out


def test_url_for_host_defaults_to_openflight_port():
    assert url_for_host("192.168.1.50") == "http://192.168.1.50:8080"


def test_url_for_host_accepts_explicit_port():
    assert url_for_host("192.168.1.50", 9000) == "http://192.168.1.50:9000"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest catcher/tests/test_openflight_enrich.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'catcher.openflight_enrich'`

- [ ] **Step 4: Write the implementation**

Create `catcher/openflight_enrich.py`:

```python
"""Additive enrichment channel for OpenFlight launch monitors.

OpenFlight streams shots to us over GSPro OpenConnect (TCP 921), but that wire
format cannot express whether a number was measured or modelled. Its own web UI
gets the full truth over Socket.IO, so we subscribe to the same `shot` event and
recover per-field source/confidence plus real nulls.

Strictly additive: this module never persists anything and never blocks shot
ingest. If OpenFlight is unreachable or its payload shape changes, shots keep
arriving over the socket and simply fall back to conservative trust tiers.

We call OpenFlight's API over the network; no OpenFlight code is imported or
vendored (it is AGPL-3.0, this project is MIT).
"""
import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_WEB_PORT = 8080          # OpenFlight's Flask/Socket.IO default (--web-port)
MDNS_HOST = "openflight.local"   # advertised via Avahi by OpenFlight
SHOT_EVENT = "shot"


def url_for_host(host: str, port: int = DEFAULT_WEB_PORT) -> str:
    """Base HTTP URL for an OpenFlight host."""
    return f"http://{host}:{port}"


def normalize_event(payload) -> Optional[dict]:
    """Extract the shot dict from a Socket.IO `shot` event payload.

    Accepts both the documented `{"shot": {...}, "stats": {...}}` envelope and a
    bare shot dict. Returns None for anything unusable, including a shot with no
    ball speed (the correlation key). Unknown extra keys are preserved so the
    trust policy can use them if it learns to.
    """
    if not isinstance(payload, dict):
        return None
    shot = payload.get("shot") if isinstance(payload.get("shot"), dict) else payload
    if not isinstance(shot, dict):
        return None
    speed = shot.get("ball_speed_mph")
    try:
        float(speed)
    except (TypeError, ValueError):
        return None
    return shot


class OpenFlightEnrichClient:
    """Connects to one OpenFlight host and forwards normalized shot records.

    `on_enrichment(record: dict)` is called for every usable shot event.
    `on_status(state: str, detail: str)` reports "connected" / "disconnected" /
    "unavailable" for the Connect screen.
    """

    def __init__(self, host: str, *, port: int = DEFAULT_WEB_PORT,
                 on_enrichment: Optional[Callable[[dict], None]] = None,
                 on_status: Optional[Callable[[str, str], None]] = None):
        self.host = host
        self.port = port
        self.on_enrichment = on_enrichment or (lambda record: None)
        self.on_status = on_status or (lambda state, detail: None)
        self._sio = None
        self._thread = None
        self._running = False

    @property
    def url(self) -> str:
        return url_for_host(self.host, self.port)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        sio = self._sio
        if sio is not None:
            try:
                sio.disconnect()
            except Exception:
                pass

    def is_connected(self) -> bool:
        sio = self._sio
        return bool(sio is not None and getattr(sio, "connected", False))

    def _run(self) -> None:
        try:
            import socketio  # python-socketio[client]
        except ImportError:
            # Optional dependency: degrade to no enrichment rather than crash.
            logger.info("[openflight] python-socketio missing; enrichment disabled")
            self.on_status("unavailable", "python-socketio not installed")
            self._running = False
            return

        # The library owns reconnect/backoff; we just keep the client alive.
        sio = socketio.Client(reconnection=True, reconnection_delay=2,
                              reconnection_delay_max=30, logger=False,
                              engineio_logger=False)
        self._sio = sio

        @sio.event
        def connect():
            self.on_status("connected", self.url)

        @sio.event
        def disconnect():
            self.on_status("disconnected", self.url)

        @sio.on(SHOT_EVENT)
        def _on_shot(payload):
            record = normalize_event(payload)
            if record is None:
                return
            try:
                self.on_enrichment(record)
            except Exception:
                logger.debug("[openflight] enrichment handler failed", exc_info=True)

        try:
            sio.connect(self.url, transports=["websocket", "polling"])
            sio.wait()
        except Exception as e:
            # Unreachable host, refused connection, protocol error: all non-fatal.
            logger.info("[openflight] enrichment unavailable at %s: %s", self.url, e)
            self.on_status("disconnected", str(e))
        finally:
            self._running = False
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest catcher/tests/test_openflight_enrich.py -v`
Expected: PASS, 7 tests

- [ ] **Step 6: Commit**

```bash
git add catcher/openflight_enrich.py catcher/tests/test_openflight_enrich.py requirements-dev.txt
git commit -m "feat(catcher): OpenFlight Socket.IO enrichment client"
```

---

## Task 6: Wire enrichment into the capture supervisor

Zero-config discovery: the Pi's IP comes from the connection it opened to us.

**Files:**
- Modify: `web/backend/capture.py:110` (`handle_message`), plus `__init__` and a new helper
- Test: `web/backend/tests/test_capture_enrichment.py`

- [ ] **Step 1: Write the failing test**

Create `web/backend/tests/test_capture_enrichment.py`:

```python
import json

from web.backend.capture import CaptureSupervisor, CaptureEventBus
from web.backend.tests.conftest import seed_player
from store import repo


OPENFLIGHT_MSG = {
    "DeviceID": "OpenFlight",
    "ShotNumber": 1,
    "BallData": {"Speed": 148.2, "VLA": 13.8, "CarryDistance": 232.0,
                 "TotalSpin": 2710.0, "HLA": 0.0, "SpinAxis": 0.0},
    "ClubData": {"Speed": 0.0, "AngleOfAttack": 0.0, "FaceToTarget": 0.0,
                 "Path": 2.1},
    "ShotDataOptions": {"ContainsClubData": False, "IsHeartBeat": False},
}


def _supervisor(conn):
    sup = CaptureSupervisor(conn=conn, bus=CaptureEventBus(),
                            listener_factory=lambda **kw: None)
    return sup


def test_enrichment_is_attached_to_the_shot(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    # Enrichment arrives first, as it does in practice (same physical shot).
    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 2710,
                       "spin_rpm_measured": 2710})
    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    assert saved is not None
    stored = repo.get_shot(conn, saved.id)
    assert json.loads(stored.enrichment_json)["spin_rpm_measured"] == 2710


def test_enrichment_arriving_after_the_shot_is_attached(conn):
    """The two channels race: handle the shot-first ordering too."""
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    assert repo.get_shot(conn, saved.id).enrichment_json is None

    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 2710,
                       "spin_rpm_measured": 2710})

    stored = repo.get_shot(conn, saved.id)
    assert json.loads(stored.enrichment_json)["spin_rpm_measured"] == 2710


def test_late_enrichment_matches_only_one_shot(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    first = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    second = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 1})

    enriched = [s for s in (first, second)
                if repo.get_shot(conn, s.id).enrichment_json is not None]
    assert len(enriched) == 1


def test_shot_persists_without_enrichment(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    assert saved is not None
    assert repo.get_shot(conn, saved.id).enrichment_json is None


def test_openflight_host_learned_from_connection_source(conn):
    sup = _supervisor(conn)
    assert sup.openflight_host is None
    sup.note_source("OpenFlight", "192.168.1.50:54321")
    assert sup.openflight_host == "192.168.1.50"


def test_non_openflight_device_does_not_set_host(conn):
    sup = _supervisor(conn)
    sup.note_source("GARMIN-R50", "192.168.1.77:5000")
    assert sup.openflight_host is None


def test_probe_style_source_is_parsed(conn):
    sup = _supervisor(conn)
    sup.note_source("OpenFlight", "PROBE->192.168.1.50:921")
    assert sup.openflight_host == "192.168.1.50"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest web/backend/tests/test_capture_enrichment.py -v`
Expected: FAIL with `AttributeError: 'CaptureSupervisor' object has no attribute 'on_enrichment'`

- [ ] **Step 3: Write the implementation**

In `web/backend/capture.py`, add to the imports at the top (`json`, `threading`, and
`time` may already be present — do not duplicate them):

```python
import json
import threading
import time

from store import repo
from catcher.enrich_buffer import EnrichBuffer, SPEED_TOLERANCE
from catcher.openflight_enrich import OpenFlightEnrichClient
```

Add this module-level constant next to `_GSPRO_CLUB_CODES` (or above the class if
Task 7 has not run yet):

```python
# How long a persisted shot stays eligible for late enrichment.
_ENRICH_WINDOW_S = 5.0
```

In `CaptureSupervisor.__init__`, after `self._shot_count = 0`, add:

```python
        # OpenFlight enrichment: additive, discovered from the inbound connection.
        self._enrich_buffer = EnrichBuffer()
        self._enrich_client = None
        self._enrich_lock = threading.Lock()
        # [shot_id, ball_speed, monotonic_ts, enriched] for the shot-first race.
        self._recent_shots = []
        self.openflight_host = None
        self.enrichment_status = "idle"
```

Add these methods to `CaptureSupervisor` (place them directly above
`handle_message`):

```python
    def on_enrichment(self, record: dict):
        """Callback for the OpenFlight enrichment client.

        Correlation is bidirectional because the channels race: OpenFlight emits
        its Socket.IO event and sends the OpenConnect payload from the same
        handler, so either can arrive first.
          * enrichment first -> buffer it for handle_message() to claim
          * shot first       -> attach it to the row we just persisted
        """
        if self._attach_to_recent_shot(record.get("ball_speed_mph"), record):
            return
        self._enrich_buffer.add_enrichment(record)

    def _attach_to_recent_shot(self, ball_speed, record) -> bool:
        """Attach `record` to a recent, not-yet-enriched shot. True if attached."""
        try:
            target = float(ball_speed)
        except (TypeError, ValueError):
            return False
        cutoff = time.monotonic() - _ENRICH_WINDOW_S
        with self._enrich_lock:
            for entry in reversed(self._recent_shots):
                if entry[3] or entry[2] < cutoff:
                    continue
                if abs(entry[1] - target) <= SPEED_TOLERANCE:
                    entry[3] = True
                    shot_id = entry[0]
                    break
            else:
                return False
        try:
            repo.set_shot_enrichment(self.conn, shot_id, json.dumps(record))
        except Exception:
            return False   # enrichment must never break ingest
        return True

    def _note_recent_shot(self, shot):
        """Make a persisted shot eligible for late enrichment."""
        if shot.ball_speed is None:
            return
        now = time.monotonic()
        with self._enrich_lock:
            self._recent_shots = [e for e in self._recent_shots
                                  if e[2] >= now - _ENRICH_WINDOW_S]
            self._recent_shots.append([shot.id, float(shot.ball_speed), now, False])

    def note_source(self, device_id, source: str):
        """Learn the OpenFlight host from the connection it opened to us, and
        start the enrichment client the first time we see that device.

        `source` is "ip:port" for inbound connections or "PROBE->ip:port" for the
        outbound probe path.
        """
        if device_id != "OpenFlight" or not source:
            return
        addr = source.split("->")[-1]
        host = addr.rsplit(":", 1)[0].strip()
        if not host or host == self.openflight_host:
            return
        self.openflight_host = host
        self._start_enrichment(host)

    def _start_enrichment(self, host: str):
        if self._enrich_client is not None:
            self._enrich_client.stop()

        def _status(state, detail):
            self.enrichment_status = state
            self.bus.publish("enrichment_status", {"state": state, "detail": detail})

        self._enrich_client = OpenFlightEnrichClient(
            host, on_enrichment=self.on_enrichment, on_status=_status)
        self._enrich_client.start()
```

In `handle_message`, immediately after the `shot is None` heartbeat guard, add:

```python
        self.note_source(shot.device_id, source)
```

Then, in `handle_message`, replace this existing line:

```python
        saved = self.persister.save(self.conn, shot)
```

with:

```python
        enrichment = self._enrich_buffer.take_for(shot.ball_speed)
        if enrichment is not None:
            shot.enrichment_json = json.dumps(enrichment)
        saved = self.persister.save(self.conn, shot)
```

Then, immediately after the `if saved is None: return None` guard that follows it,
register the shot for the late-enrichment path:

```python
        if saved.enrichment_json is None:
            self._note_recent_shot(saved)
```

Finally, in `stop()` (alongside the existing listener teardown), add:

```python
        if self._enrich_client is not None:
            self._enrich_client.stop()
            self._enrich_client = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/backend/tests/test_capture_enrichment.py -v`
Expected: PASS, 7 tests

- [ ] **Step 5: Run the full backend suite for regressions**

Run: `python -m pytest -q`
Expected: PASS (441+ passed, 1 skipped)

- [ ] **Step 6: Commit**

```bash
git add web/backend/capture.py web/backend/tests/test_capture_enrichment.py
git commit -m "feat(capture): correlate OpenFlight enrichment with wire shots"
```

---

## Task 7: Push the active club to the monitor

Without this, OpenFlight believes a driver is in play on every shot and uses driver constants for its estimates.

**Files:**
- Modify: `catcher/openconnect.py`, `web/backend/capture.py:180` (`set_active_club`)
- Test: `catcher/tests/test_openconnect.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `catcher/tests/test_openconnect.py`:

```python
def test_send_player_update_writes_201_with_club():
    """A club change pushes a Player message on the live connection."""
    sent = []

    class FakeSock:
        def sendall(self, data):
            sent.append(data)

    lst = OpenConnectListener(port=0, handedness="RH")
    lst._conns.append(FakeSock())
    lst.send_player_update(club="I7")

    payload = json.loads(sent[0].decode("utf-8"))
    assert payload["Code"] == 201
    assert payload["Player"]["Club"] == "I7"
    assert payload["Player"]["Handed"] == "RH"


def test_send_player_update_survives_dead_socket():
    class DeadSock:
        def sendall(self, data):
            raise OSError("broken pipe")

    lst = OpenConnectListener(port=0)
    lst._conns.append(DeadSock())
    lst.send_player_update(club="DR")   # must not raise
```

Add `import json` to the top of the test file if it is not already imported.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest catcher/tests/test_openconnect.py -v`
Expected: FAIL with `AttributeError: 'OpenConnectListener' object has no attribute '_conns'`

- [ ] **Step 3: Write the implementation**

In `catcher/openconnect.py`, in `__init__`, after `self._threads = []`, add:

```python
        self._conns = []        # live sockets, for mid-connection Player pushes
        self.club = "DR"        # GSPro club code most recently pushed
```

In `_handle_conn`, replace the opening lines:

```python
    def _handle_conn(self, sock, source):
        self.on_status("connected", source)
        self._send(sock, {"Code": 201, "Message": "SUCCESS",
                          "Player": {"Handed": self.handedness, "Club": "DR"}})
```

with:

```python
    def _handle_conn(self, sock, source):
        self.on_status("connected", source)
        self._conns.append(sock)
        self._send(sock, {"Code": 201, "Message": "SUCCESS",
                          "Player": {"Handed": self.handedness,
                                     "Club": self.club}})
```

In `_handle_conn`'s `finally:` block, before the existing `sock.close()`, add:

```python
            try:
                self._conns.remove(sock)
            except ValueError:
                pass
```

Add this method after `set_handedness`:

```python
    def send_player_update(self, *, club: Optional[str] = None,
                           handedness: Optional[str] = None):
        """Push a Player message to every live connection.

        OpenConnect carries player state on a 201, so a club change is just
        another 201. Monitors that estimate unmeasured fields per club (e.g.
        OpenFlight) need this to pick the right model. Best-effort: a dead
        socket is skipped, never raised.
        """
        if club is not None:
            self.club = club
        if handedness is not None:
            self.handedness = handedness
        payload = {"Code": 201, "Message": "SUCCESS",
                   "Player": {"Handed": self.handedness, "Club": self.club}}
        for sock in list(self._conns):
            self._send(sock, payload)
```

In `web/backend/capture.py`, add this module-level mapping above the
`CaptureSupervisor` class:

```python
# GarageTEC club names -> GSPro Open Connect club codes.
_GSPRO_CLUB_CODES = {
    "Driver": "DR", "3 Wood": "W3", "5 Wood": "W5", "Hybrid": "H3",
    "3 Iron": "I3", "4 Iron": "I4", "5 Iron": "I5", "6 Iron": "I6",
    "7 Iron": "I7", "8 Iron": "I8", "9 Iron": "I9", "PW": "PW",
}
```

Then in `set_active_club`, after `self.active_club = club or None`, add:

```python
        code = _GSPRO_CLUB_CODES.get(self.active_club or "")
        if code and self._listener is not None:
            try:
                self._listener.send_player_update(club=code)
            except Exception:
                pass  # pushing club is best-effort; never block the UI
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest catcher/tests/test_openconnect.py -v`
Expected: PASS, existing tests plus the 2 new ones

- [ ] **Step 5: Commit**

```bash
git add catcher/openconnect.py web/backend/capture.py catcher/tests/test_openconnect.py
git commit -m "feat(catcher): push active club to the launch monitor on change"
```

---

## Task 8: Expose tiers through the API

**Files:**
- Modify: `web/backend/api_swings.py:13` (`_swing_detail`)
- Test: `web/backend/tests/test_api_swings.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `web/backend/tests/test_api_swings.py`:

```python
def test_swing_detail_includes_trust_tiers(client, conn):
    from store.models import Shot
    from web.backend.tests.conftest import seed_player
    import json as _json

    player = seed_player(conn, "T")
    sid = repo.create_session(conn, player.id).id
    swing = repo.add_swing(conn, sid, player.id, "v.mp4")
    shot = repo.save_shot(conn, Shot(captured_at="2026-08-10T00:00:00+00:00",
                                     player_id=player.id, session_id=sid,
                                     ball_speed=148.2, vla=13.8,
                                     enrichment_json=_json.dumps({
                                         "ball_speed_mph": 148.2,
                                         "launch_angle_vertical": 13.8,
                                         "launch_angle_vertical_confidence": 0.2,
                                     })))
    repo.link_shot_to_swing(conn, shot.id, swing.id)

    body = client.get(f"/api/swings/{swing.id}").json()
    assert body["trust"]["ball_speed"] == "measured"
    assert body["trust"]["vla"] == "estimated"      # confidence below the bar


def test_swing_detail_trust_present_without_enrichment(client, conn):
    p = seed_player(conn, "U")
    swing = seed_ready_swing(conn, p)
    body = client.get(f"/api/swings/{swing.id}").json()
    assert body["trust"]["ball_speed"] == "measured"
    assert body["trust"]["attack_angle"] == "absent"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest web/backend/tests/test_api_swings.py -v`
Expected: FAIL with `KeyError: 'trust'`

- [ ] **Step 3: Write the implementation**

In `web/backend/api_swings.py`, add to the imports:

```python
import json

from catcher import trust as trust_mod
```

In `_swing_detail`, add a `"trust"` key to the returned dict (after `"ball_raw"`):

```python
        "trust": trust_mod.derive_tiers(
            json.loads(shot.enrichment_json)
            if shot is not None and shot.enrichment_json else None
        ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/backend/tests/test_api_swings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/backend/api_swings.py web/backend/tests/test_api_swings.py
git commit -m "feat(api): expose per-field trust tiers on swing detail"
```

---

## Task 9: Tier-aware AI coach

Estimated numbers may inform the read, but must never be asserted as measured fact.

**Files:**
- Modify: `coach/context.py:58` (`build_swing_context`), `coach/prompt.py:9` (SYSTEM)
- Test: `coach/tests/test_context.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `coach/tests/test_context.py`:

```python
def test_swing_context_marks_estimated_ball_fields(db):
    import json
    from store import repo
    from store.models import Shot

    pid = repo.get_or_create_player(db, "Est", 70.0, "R").id
    sid = repo.create_session(db, pid).id
    swing = repo.add_swing(db, sid, pid, "v.mp4")
    shot = repo.save_shot(db, Shot(captured_at="2026-08-10T00:00:00+00:00",
                                   player_id=pid, session_id=sid,
                                   ball_speed=148.2, total_spin=2500.0,
                                   enrichment_json=json.dumps({
                                       "ball_speed_mph": 148.2,
                                       "spin_rpm": 2500,
                                       "spin_rpm_measured": None,
                                   })))
    repo.link_shot_to_swing(db, shot.id, swing.id)

    ctx = context.build_swing_context(db, swing.id)
    assert ctx["shot_trust"]["ball_speed"] == "measured"
    assert ctx["shot_trust"]["total_spin"] == "estimated"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest coach/tests/test_context.py -v`
Expected: FAIL with `KeyError: 'shot_trust'`

- [ ] **Step 3: Write the implementation**

In `coach/context.py`, add to the imports:

```python
import json

from catcher import trust as trust_mod
```

In `build_swing_context`, add a `shot_trust` key to the returned dict (after
`"shot": _shot_dict(shot),`):

```python
        "shot_trust": trust_mod.derive_tiers(
            json.loads(shot.enrichment_json)
            if shot is not None and shot.enrichment_json else None
        ),
```

In `coach/prompt.py`, in the `SYSTEM` string, replace this sentence:

```python
    "(4) For metrics flagged history-only or low confidence, say so "
    "plainly and temper your certainty accordingly. "
```

with:

```python
    "(4) For metrics flagged history-only or low confidence, say so "
    "plainly and temper your certainty accordingly. When `shot_trust` marks a "
    "ball/club field 'estimated', that number was MODELLED by the launch "
    "monitor, not measured: you may use it for context but must never present "
    "it as a measured fact, never build a worst-offender finding on it alone, "
    "and never compare it to a tour range as if it were real. Fields marked "
    "'absent' were not measured at all -- ignore them entirely. "
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest coach/tests/ -v`
Expected: PASS, all coach tests including the new one

- [ ] **Step 5: Commit**

```bash
git add coach/context.py coach/prompt.py coach/tests/test_context.py
git commit -m "feat(coach): withhold estimated launch-monitor values from findings"
```

---

## Task 10: Frontend estimated marker

**Files:**
- Modify: `web/frontend/src/lib/types.ts`, `web/frontend/src/components/MetricCard.tsx`
- Test: `web/frontend/src/components/MetricCard.test.tsx`

- [ ] **Step 1: Write the failing test**

Append to the existing `web/frontend/src/components/MetricCard.test.tsx` (match the
imports and props style already used in that file; `MetricCardProps` requires
`label`, `value`, `unit`, `target`, `delta`, `zone`, `state`):

```tsx
describe("MetricCard estimated marker", () => {
  const base = {
    label: "Spin Rate", value: 2500, unit: "rpm",
    target: 2686, delta: -186, zone: "red" as const, state: "ok" as const,
  };

  it("marks an estimated value", () => {
    render(<MetricCard {...base} estimated />);
    expect(screen.getByTitle(/estimated by the launch monitor/i)).toBeInTheDocument();
  });

  it("suppresses the zone dot when estimated", () => {
    const { container } = render(<MetricCard {...base} estimated />);
    expect(container.querySelector(".bg-garage-red")).toBeNull();
  });

  it("shows no marker and keeps the zone for a measured value", () => {
    const { container } = render(<MetricCard {...base} />);
    expect(screen.queryByTitle(/estimated by the launch monitor/i)).toBeNull();
    expect(container.querySelector(".bg-garage-red")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web/frontend && ./node_modules/.bin/vitest run src/components/MetricCard.test.tsx`
Expected: FAIL — no `estimated` prop, marker not found

- [ ] **Step 3: Write the implementation**

In `web/frontend/src/lib/types.ts`, add:

```ts
export type TrustTier = "measured" | "estimated" | "absent";
export type TrustMap = Record<string, TrustTier>;
```

Add `trust?: TrustMap;` to the `SwingDetail` interface.

In `web/frontend/src/components/MetricCard.tsx`:

**(a)** Add to `MetricCardProps` (after `compact?: boolean` at line 50):

```tsx
  estimated?: boolean     // monitor-modelled value: show a marker, never grade it
```

**(b)** Add `estimated` to the destructured parameter list (line 61-63), e.g.
`label, value, unit, target, delta, zone, state, trend, estimated,`.

**(c)** Suppress grading with a single change at line 79. Replace:

```tsx
  const zoned = state === 'ok' && zone
```

with:

```tsx
  // An estimated value is never graded: no tint, no dot, no coloured delta.
  const zoned = state === 'ok' && zone && !estimated
```

This one edit already neutralizes `zoneBorder`, `zoneWash`, `deltaColor`, and the
zone dot, because all four derive from `zoned`.

**(d)** Render the marker. Inside the value row, immediately after the element that
prints `fmt(value, unit)`, add:

```tsx
{estimated && (
  <span
    title="Estimated by the launch monitor, not measured"
    className="ml-1 align-super text-[10px] font-semibold text-[#8B978F]"
  >
    *est
  </span>
)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web/frontend && ./node_modules/.bin/vitest run src/components/MetricCard.test.tsx`
Expected: PASS, 2 tests

- [ ] **Step 5: Run the full frontend suite and typecheck**

Run: `cd web/frontend && npx tsc --noEmit && ./node_modules/.bin/vitest run`
Expected: typecheck clean; all tests pass

- [ ] **Step 6: Commit**

```bash
git add web/frontend/src/lib/types.ts web/frontend/src/components/MetricCard.tsx web/frontend/src/components/MetricCard.test.tsx
git commit -m "feat(ui): mark launch-monitor estimates and skip their tour grade"
```

---

## Task 11: Show enrichment status on Connect

Spec §3.1 requires a visible status line so the user can tell enrichment is live without touching a config file.

**Files:**
- Modify: `web/backend/capture.py` (`CaptureStatus` + `status()`), `web/frontend/src/lib/types.ts`, `web/frontend/src/pages/ConnectScreen.tsx`
- Test: `web/backend/tests/test_capture_enrichment.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `web/backend/tests/test_capture_enrichment.py`:

```python
def test_status_reports_enrichment_fields(conn):
    sup = _supervisor(conn)
    st = sup.status()
    assert st.enrichment_status == "idle"
    assert st.openflight_host is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest web/backend/tests/test_capture_enrichment.py::test_status_reports_enrichment_fields -v`
Expected: FAIL with `AttributeError: 'CaptureStatus' object has no attribute 'enrichment_status'`

- [ ] **Step 3: Write the implementation**

In `web/backend/capture.py`, add two fields to the `CaptureStatus` dataclass after
`active_club: Optional[str]`:

```python
    enrichment_status: str = "idle"
    openflight_host: Optional[str] = None
```

In `status()`, add them to the returned `CaptureStatus(...)` after
`active_club=self.active_club,`:

```python
                enrichment_status=self.enrichment_status,
                openflight_host=self.openflight_host,
```

In `web/frontend/src/lib/types.ts`, add to the `CaptureStatus` interface:

```ts
  enrichment_status: string;
  openflight_host: string | null;
```

In `web/frontend/src/pages/ConnectScreen.tsx`, render a status row wherever the
existing monitor/connection details are listed:

```tsx
{captureStatus?.openflight_host && (
  <div className="flex items-center gap-2 text-sm">
    <span className={cn('w-2 h-2 rounded-full',
      captureStatus.enrichment_status === 'connected'
        ? 'bg-garage-green' : 'bg-garage-amber')} />
    <span className="text-[#8B978F]">
      OpenFlight enrichment:{' '}
      <span className="text-[#E7EEE9]">
        {captureStatus.enrichment_status === 'connected'
          ? `connected (${captureStatus.openflight_host})`
          : 'not connected — measured/estimated detail unavailable'}
      </span>
    </span>
  </div>
)}
```

Confirm `cn` is imported in `ConnectScreen.tsx` (`import { cn } from '../lib/utils'`);
add it if missing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest web/backend/tests/ -q`
Expected: PASS

Run: `cd web/frontend && npx tsc --noEmit`
Expected: clean

- [ ] **Step 5: Commit**

```bash
git add web/backend/capture.py web/frontend/src/lib/types.ts web/frontend/src/pages/ConnectScreen.tsx web/backend/tests/test_capture_enrichment.py
git commit -m "feat(connect): surface OpenFlight enrichment status"
```

---

## Task 12: Bundle the dependency and verify end to end

**Files:**
- Modify: `garagetec.spec`

- [ ] **Step 1: Add the hidden imports**

In `garagetec.spec`, add to the `hiddenimports` list (beside `'anthropic'`):

```python
    'socketio',                # python-socketio client (OpenFlight enrichment)
    'engineio',
    'engineio.async_drivers.threading',
```

- [ ] **Step 2: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS, all backend tests

Run: `cd web/frontend && npx tsc --noEmit && ./node_modules/.bin/vitest run`
Expected: typecheck clean, all frontend tests pass

- [ ] **Step 3: Rebuild the frontend and the desktop app**

Run: `cd web/frontend && npm run build`
Expected: `built in ...`

Run: `python -m PyInstaller garagetec.spec --noconfirm --distpath dist_app --workpath build_pyi`
Expected: `Build complete!`

- [ ] **Step 4: Smoke-test the packaged app**

Run: `./dist_app/GarageTEC/GarageTEC.exe --no-window --no-browser`
Expected: server starts; `curl -s http://127.0.0.1:8000/api/health` returns
`{"status":"ok"}`. No `launch-error.log` in `%LOCALAPPDATA%\GarageTEC`.
Stop it with `taskkill //IM GarageTEC.exe //F`.

- [ ] **Step 5: Simulate an OpenFlight shot against the running dev server**

Start the dev server: `python -m uvicorn web.backend.app:app --port 8000`

Then run this script to act as OpenFlight's GSPro client:

```python
import json, socket
msg = {
    "DeviceID": "OpenFlight", "Units": "Yards", "ShotNumber": 1,
    "APIversion": "1",
    "BallData": {"Speed": 121.4, "SpinAxis": 0.0, "TotalSpin": 7000.0,
                 "BackSpin": 7000.0, "SideSpin": 0.0, "HLA": 0.0,
                 "VLA": 16.3, "CarryDistance": 171.0},
    "ClubData": {"Speed": 0.0, "AngleOfAttack": 0.0, "FaceToTarget": 0.0,
                 "Path": 2.1},
    "ShotDataOptions": {"ContainsBallData": True, "ContainsClubData": False,
                        "LaunchMonitorIsReady": True,
                        "LaunchMonitorBallDetected": True,
                        "IsHeartBeat": False},
}
s = socket.create_connection(("127.0.0.1", 921), timeout=5)
print("handshake:", s.recv(4096).decode())
s.sendall(json.dumps(msg).encode())
print("ack:", s.recv(4096).decode())
s.close()
```

Expected: handshake shows `"Code": 201` with a `Player` block; ack shows
`"Code": 200`. Select a player and start a session in the UI first, otherwise the
shot is intentionally dropped with `shot_dropped_no_session`.

Then confirm the stored row nulled the padded zeros:

```bash
python -c "from store import db as d; c=d.connect(); r=c.execute('SELECT device_id,ball_speed,hla,spin_axis,club_speed,attack_angle FROM shot ORDER BY id DESC LIMIT 1').fetchone(); print(dict(r))"
```

Expected: `device_id='OpenFlight'`, `ball_speed=121.4`, and `hla`, `spin_axis`,
`club_speed`, `attack_angle` all `None`.

- [ ] **Step 6: Commit**

```bash
git add garagetec.spec
git commit -m "build: bundle python-socketio for OpenFlight enrichment"
```

---

## Deferred (explicitly out of scope)

Per spec §8, not in this plan:

- Multiple monitors active simultaneously.
- Reading OpenFlight's JSONL logs or backfilling historical sessions.
- An upstream PR adding provenance to OpenFlight's GSPro connector (would let us
  delete the enrichment channel entirely).
- README hardware-section updates for the OpenFlight build option.
- Bay validation against real OpenFlight hardware: add to
  `docs/bay-verification-checklist.md` when a rig exists.
