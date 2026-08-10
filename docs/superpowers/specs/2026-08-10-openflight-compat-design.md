# OpenFlight launch-monitor compatibility — design

**Created:** 2026-08-10
**Status:** approved, ready for implementation planning

Lets GarageTEC ingest shots from [OpenFlight](https://github.com/jewbetcha/openflight),
an open-source DIY radar launch monitor (~$400), as an alternative to the Garmin
Approach R50. The R50 path is unchanged.

**Why:** GarageTEC's differentiator is two-camera body analysis, tour benchmarking, and
AI coaching, none of which require an R50. Supporting OpenFlight means someone can
build the entire bay from open hardware without buying a commercial launch monitor.

---

## 1. Verified facts about OpenFlight

Established by reading the repo at 2026-08-10 (commit stream active that day).

**It already speaks our protocol.** OpenFlight is a **GSPro OpenConnect V1 client**
over TCP 921. GarageTEC's `catcher/openconnect.py` binds `0.0.0.0:921` and acts as the
GSPro *server*. OpenFlight dials out to a configured `host:port`, so the topology
matches with no protocol work.

Handshake compatibility, verified against `src/openflight/gspro/codec.py`:

| GarageTEC sends | OpenFlight's `parse_inbound` |
|---|---|
| `{"Code":201,...,"Player":{"Handed":…,"Club":…}}` on connect | → `PlayerUpdate` (it adopts our handedness and club) |
| `{"Code":200,"Message":"OK"}` per shot | → `ShotAck(ok=True)` |
| n/a | heartbeats arrive with `IsHeartBeat: true`; our `is_heartbeat()` reads that exact field |

Their payload schema (`src/openflight/gspro/messages.py`) is a 1:1 name match with
`catcher/shotmap.py`. Their serializer emits compact JSON with no trailing newline;
our stream parser already tolerates both newline-delimited and concatenated objects.

**It fabricates values it cannot measure.** Because its primary consumer is a
*simulator* (which cannot fly a ball without spin and launch angle),
`src/openflight/sim/resolver.py` substitutes per-club constants when a measurement is
missing:

| Field | Measured when | Otherwise sent as |
|---|---|---|
| ball speed | always (required) | `IncompleteShotError`, shot rejected |
| carry | always model-derived (ballistic) | flagged by whether launch angle was real |
| VLA | angle radar or camera present | per-club constant (`_OPTIMAL_LAUNCH`) |
| HLA | if measured | `0.0` |
| total spin | measured **and** high confidence | per-club constant (`SPIN_MODEL_RPM`) |
| spin axis | if measured | `0.0` |
| club speed | if detected | `None` → serialized as `0.0` |

This is not dishonest: OpenFlight tags every field `measured` or `estimated` in a
`provenance` dict and badges it in its own UI. **But OpenConnect V1 has no provenance
field, so all of it is lost on the wire.** Absent values arrive as literal `0.0`
because their dataclasses default to `0.0` rather than null.

**Angle measurement is implemented today.** `src/openflight/iwr6843/` is a full package
(driver, DOA, MUSIC, multipath, tracking, trajectory, club path, calibration) with
custom C firmware, plus a separate camera path at
`src/openflight/camera/launch_angle.py`. We assume the angle radar is present for all
users, so no capability setting is needed.

**A richer local channel exists.** `server.py`'s `shot_to_dict()` exposes the full
truth, including `launch_angle_vertical_source`, `launch_angle_vertical_confidence`,
`angle_source`, `spin_source`, `spin_method`, `spin_confidence`, `spin_quality`,
`spin_rpm_measured`, `carry_range`, and **real `None`s instead of `0.0`**. It is
broadcast as `socketio.emit("shot", {"shot": shot_to_dict(shot), "stats": stats})` on
their Flask-SocketIO server (default port **8080**, `--web-port`), and mirrored into
JSONL session logs.

**Licensing.** OpenFlight is **AGPL-3.0**; GarageTEC is MIT. We speak its protocol and
call its API. **No OpenFlight source may be copied or vendored into this repo** — that
would make GarageTEC's MIT licensing untenable. The boundary is the socket.

---

## 2. Current GarageTEC defects this exposes

Present in our code today, independent of OpenFlight:

1. **`ContainsClubData` is ignored.** `shotmap.map_message()` reads the `ClubData` block
   unconditionally. OpenFlight always sends the block and honestly sets
   `ContainsClubData: false` when it has no club speed. Result: we would store
   `club_speed=0.0`, `attack_angle=0.0`, `face_to_target=0.0` as real measurements,
   then grade `0.0` against a 113 mph tour driver average.
2. **The club is hardcoded in the handshake.** We send `"Club": "DR"` on connect and
   never push updates; `set_active_club()` only publishes to our own event bus. So
   OpenFlight believes a driver is in play on every shot and uses *driver* constants for
   its estimates, while GarageTEC tags the shot with the real club and benchmarks it
   against, say, the 7-iron average. Guaranteed false red.

Smash factor is already guarded (`cs > 0` → `None`), so there is no divide-by-zero.

---

## 3. Architecture: two channels, one load-bearing

```
OpenFlight (Raspberry Pi)
  |
  |-- GSPro OpenConnect V1 --> TCP 921 --> existing GarageTEC listener   [LOAD-BEARING]
  |      canonical shot; triggers camera capture; stable documented protocol
  |
  \-- Socket.IO "shot" event --> enrichment client                       [ADDITIVE]
         provenance: sources, confidences, real nulls, carry_range
```

**Why not Socket.IO alone?** It is tempting (one connection, no correlation) but it
makes an unversioned internal channel load-bearing: a renamed event or field would mean
*zero shots ingested*. With the split, their stable documented protocol carries the
shot and enrichment is additive. If enrichment breaks, every swing is still captured,
just treated conservatively.

**Capture trigger is unchanged.** The GSPro shot still drives
`live_capture.on_shot()`, so video timing behaves exactly as with the R50. Enrichment
arrives afterward and updates the stored row.

### 3.1 Zero-config address discovery

The user enters nothing. OpenFlight dials *us*, so we already know its address:
`_handle_conn` receives `addr[0]` and passes it to `handle_message` as `source`.

Resolution order:

1. **IP from the inbound GSPro connection** (works on any network, no config)
2. `openflight.local:8080` via their advertised Avahi mDNS
3. Manual override field on Connect — only needed if `--web-port` was changed

Connect shows a status line (`OpenFlight enrichment: connected`). Nothing to look up.

### 3.2 Correlation

Both channels fire from the same `Shot` object microseconds apart, and **both round ball
speed identically to one decimal** (`round(ball_speed_mph, 1)` in their GSPro codec and
in `shot_to_dict`). So ball speed matches exactly and is a strong key.

- Key: `ball_speed` to 1 dp, matched within a **±5 s** window, first-unclaimed-wins.
- A short-lived pending buffer holds enrichment records.
- If no enrichment arrives within **~2 s** of the socket shot, persist without it.
  Never delay a shot waiting on enrichment.

---

## 4. Trust model

Three tiers per field, derived from the enrichment record:

| Tier | Rule | Storage | Stoplight | UI | AI coach |
|---|---|---|---|---|---|
| **Measured** | value present, source is a real sensor, confidence ≥ `CONFIDENCE_MIN` | as today | graded vs tour | normal | full grounding |
| **Estimated** | value present but model-derived or low confidence | as today | **no grade** | value + `*` "est." marker | included, flagged estimated |
| **Absent** | null, or `0.0` sentinel for a field the device cannot produce | `NULL` | none | `--` / "No data" | withheld |

Field mapping (angle radar assumed present):

| GarageTEC | OpenFlight source | Tier signal |
|---|---|---|
| `ball_speed` | `ball_speed_mph` | always measured |
| `carry` | `estimated_carry_yards`, `carry_range` | their provenance: launch-angle-informed vs modelled |
| `vla` / `hla` | `launch_angle_vertical` / `_horizontal` | `_source` + `_confidence` |
| `total_spin` | `spin_rpm` vs `spin_rpm_measured` | `spin_source`, `spin_confidence`, `spin_quality` |
| `spin_axis` | `spin_axis_deg` | null → absent |
| `club_speed`, smash | `club_speed_mph` | real null when undetected → absent |
| `club_path` | `club_path_deg` | experimental → estimated |
| `attack_angle`, `face_to_target` | not produced | absent |
| back/side spin | derived from spin + axis | inherits the spin tier |

**Thresholds and device profiles both live in `catcher/trust.py`:**

- `CONFIDENCE_MIN = 0.7`, mirroring OpenFlight's own `SPIN_CONFIDENCE_HIGH = 0.7`
  (`src/openflight/launch_monitor.py:17`), so our "measured" bar matches the bar they
  use internally to accept a spin reading. Tunable in one place after bay testing.
- `DEVICE_PROFILES: dict[str, DeviceProfile]` keyed by the `DeviceID` string
  (OpenFlight's config default is `"OpenFlight"`), naming which fields that device can
  never produce. This is the only thing that authorizes the `0.0 → NULL` coercion.
  An unknown `DeviceID` gets the permissive R50-style profile, so no existing or future
  device regresses.

**Storage:** one nullable `enrichment_json` TEXT column on `shot`
(`store/db.py::_add_column_if_missing` already supports this migration). Tiers are
derived at **read time** by a single helper, so policy changes need no migration and no
re-seed.

### 4.1 Device-scoped zero handling

`ContainsClubData` is a universal, safe check and applies to every device.

Coercing `0.0 → NULL` is **not** universally safe: a genuinely measured HLA, spin axis,
or attack angle can legitimately be zero (a dead-straight shot). That coercion is
therefore **device-scoped** — applied only where the device profile says the field is
unproducible, never blanket. **The R50 path stays byte-identical.**

### 4.2 Club push

On club change, send a `Player` update over the open connection so OpenFlight's
fallbacks use the correct club instead of always assuming a driver. Improves our
estimated fields and their carry number. Requires a new
`OpenConnectListener.send_player_update(handed, club)`; today only the 201 handshake
carries player state.

---

## 5. Components

Following existing `catcher/` conventions: no DB access, no UI coupling, callback-driven.

| File | Role |
|---|---|
| `catcher/openflight_enrich.py` *(new)* | Socket.IO client. Subscribes to `shot`, normalizes to a `ShotEnrichment`, reconnects with backoff, hands off via callback. Mirrors `openconnect.py`'s shape. |
| `catcher/trust.py` *(new)* | **Pure policy.** `derive_tiers(enrichment) -> {field: tier}`. All thresholds in one place, zero I/O, exhaustively testable. |
| `catcher/shotmap.py` *(edit)* | Honor `ContainsClubData`; device-scoped `0.0` handling. |
| `catcher/openconnect.py` *(edit)* | Add `send_player_update(handed, club)`. |
| `web/backend/capture.py` *(edit)* | Derive the Pi's IP from `source`, start enrichment, correlate, persist, push club on change. `handle_message()` is the single choke point for all shots. |
| `coach/context.py`, `coach/prompt.py` *(edit)* | Carry tiers into grounding; temper estimated values. |
| `MetricCard`, Connect screen *(edit)* | `*`/"est." marker with tooltip; enrichment status line. |

**New dependency:** `python-socketio[client]` (their server is Flask-SocketIO, so a raw
WebSocket will not do). One package, one PyInstaller hidden-import in `garagetec.spec`.

---

## 6. Failure modes

The governing rule: **enrichment is never allowed to cost you a shot.**

| Failure | Behavior |
|---|---|
| Pi unreachable / enrichment down | Log once, retry with backoff. Shots keep landing via TCP 921; non-guaranteed fields fall to conservative tiers. |
| Their schema drifts | We read only keys we know, each defensively. A missing or renamed key degrades that one field to absent/estimated. Cannot crash ingest or block capture. |
| Correlation miss | Persist without provenance after ~2 s rather than delay the shot. |
| Late enrichment | Update the row if still within the window; otherwise drop. |
| Two shots, identical ball speed, inside the window | First-unclaimed-wins. Worst case is a provenance swap between shots whose values are identical anyway. |
| `python-socketio` not installed | Guarded import; feature silently off. |

---

## 7. Testing

Entirely fixture-driven — **no OpenFlight hardware required**, which is mandatory since
none is available.

- **`catcher/tests/test_trust.py`** — table-driven: every field × measured/estimated/absent → expected tier.
- **`catcher/tests/test_openflight_enrich.py`** — real-shaped `shot_to_dict` payloads → normalized output. Includes a deliberate **schema-drift fixture** (keys renamed/removed) asserting graceful degradation, not a crash.
- **`catcher/tests/test_shotmap.py`** *(extend)* — `ContainsClubData: false` → club fields `NULL`; OpenFlight + `0.0` → absent; **an R50 regression case proving that path is unchanged**.
- **Correlation tests** — happy path, out-of-order, timeout, duplicate-speed collision.
- **Frontend** — one test for the estimated marker.

---

## 8. Out of scope

- Multiple monitors active simultaneously. One monitor at a time; OpenFlight is an
  alternative, not a companion. (`device_id` is already stored, so per-shot device
  attribution comes free if it is ever wanted.)
- Reading OpenFlight's JSONL session logs, or backfilling historical sessions.
- Any upstream contribution to OpenFlight (e.g. adding provenance to their GSPro
  connector). Worth revisiting later; it would let us drop the enrichment channel.
- Vendoring any OpenFlight code (AGPL, prohibited here).
- README hardware-section updates for the OpenFlight option — a follow-up docs task
  once this works.
