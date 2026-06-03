# R50 Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `catcher/` package — a production R50 shot catcher that listens on GSPro Open Connect, maps each shot to a `store.models.Shot`, attributes it to the active player + an auto-resuming per-player session, and persists it (buffering to disk on DB failure) behind a friendly tkinter wizard.

**Architecture:** A GUI-agnostic listener (`openconnect.py`) lifted from the validated spike emits parsed message dicts via callback. A pure mapper (`shotmap.py`) turns GSPro JSON into a `Shot` (or `None` for heartbeats). `sessionmgr.py` holds active-player state and resolves the open/new session through `store.repo`. `persist.py` saves via `store.repo.save_shot`, buffering raw shots to `data/pending_shots.jsonl` on failure and replaying them on recovery. `app.py` wires these into a tkinter wizard grown from the spike; `run.py` is the entry point, packaged to a standalone exe.

**Tech Stack:** Python 3.12, stdlib only (`socket`, `threading`, `json`, `queue`, `tkinter`), the existing `store/` package (Batch 0), `pytest` (dev only), PyInstaller (packaging only). No new runtime dependencies.

Spec: `docs/superpowers/specs/2026-06-03-batch1-r50-ingest-design.md`
Reuses: `spike/gspro_spike_listener.py` (server/probe loops, tolerant JSON framing, 201 handshake, 200 ack).
Consumes (Batch 0): `store.repo.get_or_create_player`, `list_players`, `get_open_session`, `create_session`, `end_idle_sessions`, `save_shot`; `store.models.Shot`, `Player`, `Session`.

Python interpreter for all commands (py launcher is NOT on PATH):
`C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe`

---

## File Structure

- `catcher/__init__.py` — package marker.
- `catcher/openconnect.py` — `OpenConnectListener`: GUI-agnostic GSPro Open Connect server (`0.0.0.0:921`) + optional probe dialer, tolerant JSON-stream framing, 201 handshake (with active-player handedness), 200 ack per inbound message. Emits each parsed message dict to an `on_message(obj, source)` callback. Lifted from the spike's `_server_loop` / `_probe_loop` / `_handle_conn` / framing logic.
- `catcher/shotmap.py` — `map_message(obj) -> Optional[Shot]`: GSPro Open Connect JSON → `store.models.Shot` (ball + club columns + full `raw_json`); returns `None` for heartbeats.
- `catcher/sessionmgr.py` — `SessionManager`: active-player state + per-player session resolution via `store.repo` (`get_open_session` / `create_session` / `end_idle_sessions`). `attribute(conn, shot)` stamps `player_id` + `session_id`.
- `catcher/persist.py` — `ShotPersister`: `save(conn, shot, raw)` via `store.repo.save_shot`; on DB failure appends raw to `data/pending_shots.jsonl`; `replay(conn)` re-saves buffered shots and clears the buffer on success.
- `catcher/app.py` — `CatcherApp`: tkinter GUI grown from the spike wizard — connect flow, live capture screen, "Who's hitting?" active-player switch, Add-player form, live shot feed, session/connection status. Headless `--selftest` construction path.
- `catcher/run.py` — entry point; `main()` + `--selftest`; packaged to a standalone exe like the spike.
- `catcher/tests/__init__.py` — test package marker.
- `catcher/tests/conftest.py` — `db` fixture (fresh in-memory store) + `tmp_buffer` fixture.
- `catcher/tests/test_openconnect.py` — loopback test (fake R50 client) incl. concatenated-JSON framing.
- `catcher/tests/test_shotmap.py` — representative GSPro JSON → `Shot` fields + `raw_json`; heartbeat → `None`.
- `catcher/tests/test_sessionmgr.py` — brother↔you interleave/resume against the in-memory store.
- `catcher/tests/test_persist.py` — failing store buffers to file; recovery replays + clears.
- `catcher/tests/test_app.py` — construction smoke test via `run.py --selftest`.

Conventions: timestamps are ISO-8601 UTC via `store.db.now_iso()`. The listener never touches the DB or tkinter — it only emits dicts. `shotmap` is pure (no I/O). Every `store.repo` call takes an open `sqlite3.Connection` as its first argument.

---

## Task 1: Package scaffold + test fixtures

**Files:**
- Create: `catcher/__init__.py`
- Create: `catcher/tests/__init__.py`
- Create: `catcher/tests/conftest.py`

- [ ] **Step 1: Create the package files**

`catcher/__init__.py`:
```python
"""GarageTEC R50 ingest: live shot catcher + persistence."""
```

`catcher/tests/__init__.py`: (empty file)

- [ ] **Step 2: Add the test fixtures**

`catcher/tests/conftest.py`:
```python
import pytest
from store import db as dbmod


@pytest.fixture
def db():
    conn = dbmod.connect(":memory:")
    dbmod.init_db(conn=conn)
    yield conn
    conn.close()


@pytest.fixture
def tmp_buffer(tmp_path):
    return str(tmp_path / "pending_shots.jsonl")
```

- [ ] **Step 3: Run to confirm collection works (no tests yet)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/ -v`
Expected: `no tests ran` (0 collected) — confirms the package imports and the `store` fixture wiring is valid.

- [ ] **Step 4: Commit**

```bash
git add catcher/__init__.py catcher/tests/__init__.py catcher/tests/conftest.py
git commit -m "chore(catcher): scaffold package + test fixtures"
```

---

## Task 2: shotmap — GSPro JSON → Shot (and heartbeat → None)

**Files:**
- Create: `catcher/shotmap.py`
- Create: `catcher/tests/test_shotmap.py`

- [ ] **Step 1: Write the failing test**

`catcher/tests/test_shotmap.py`:
```python
import json
from catcher.shotmap import map_message, is_heartbeat
from store.models import Shot


SHOT_MSG = {
    "DeviceID": "GARMIN-R50",
    "Units": "Yards",
    "ShotNumber": 7,
    "APIversion": "1",
    "BallData": {
        "Speed": 148.2,
        "SpinAxis": -6.4,
        "TotalSpin": 2710.0,
        "HLA": 1.2,
        "VLA": 13.8,
        "CarryDistance": 232.5,
    },
    "ClubData": {
        "Speed": 102.1,
        "AngleOfAttack": -2.3,
        "Path": 2.1,
        "FaceToTarget": -0.7,
    },
    "ShotDataOptions": {
        "ContainsBallData": True,
        "ContainsClubData": True,
        "IsHeartBeat": False,
    },
}

HEARTBEAT_MSG = {
    "DeviceID": "GARMIN-R50",
    "ShotDataOptions": {
        "ContainsBallData": False,
        "ContainsClubData": False,
        "IsHeartBeat": True,
    },
}


def test_heartbeat_maps_to_none():
    assert is_heartbeat(HEARTBEAT_MSG) is True
    assert map_message(HEARTBEAT_MSG) is None


def test_shot_maps_all_fields():
    shot = map_message(SHOT_MSG)
    assert isinstance(shot, Shot)
    assert shot.device_id == "GARMIN-R50"
    assert shot.shot_number == 7
    assert shot.ball_speed == 148.2
    assert shot.total_spin == 2710.0
    assert shot.spin_axis == -6.4
    assert shot.hla == 1.2
    assert shot.vla == 13.8
    assert shot.carry == 232.5
    assert shot.club_speed == 102.1
    assert shot.attack_angle == -2.3
    assert shot.club_path == 2.1
    assert shot.face_to_target == -0.7
    # captured_at is a populated ISO-8601 string
    assert isinstance(shot.captured_at, str) and "T" in shot.captured_at
    # player/session not assigned by the mapper (sessionmgr does that)
    assert shot.player_id is None and shot.session_id is None
    # raw_json round-trips to the original message
    assert json.loads(shot.raw_json) == SHOT_MSG


def test_shot_ball_only_when_no_club():
    msg = {
        "DeviceID": "R50",
        "ShotNumber": 1,
        "BallData": {"Speed": 100.0, "VLA": 12.0, "TotalSpin": 3000.0},
        "ShotDataOptions": {"ContainsBallData": True, "ContainsClubData": False,
                            "IsHeartBeat": False},
    }
    shot = map_message(msg)
    assert shot is not None
    assert shot.ball_speed == 100.0
    assert shot.club_speed is None  # no club data present
    assert shot.club_path is None


def test_missing_shotdataoptions_is_treated_as_shot():
    # be tolerant: a message with BallData but no ShotDataOptions is still a shot
    msg = {"DeviceID": "R50", "ShotNumber": 2, "BallData": {"Speed": 90.0}}
    shot = map_message(msg)
    assert shot is not None and shot.ball_speed == 90.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_shotmap.py -v`
Expected: FAIL (`catcher.shotmap` does not exist).

- [ ] **Step 3: Write the implementation**

`catcher/shotmap.py`:
```python
"""Pure mapping from GSPro Open Connect JSON messages to store.models.Shot.

No I/O, no DB, no tkinter. Distinguishes shots from heartbeats. Stores whatever
ball/club fields arrive plus the full original message in raw_json; no field is
assumed mandatory (the R50 may send ball-only or include club data).
"""
import json
from typing import Optional

from store import db as dbmod
from store.models import Shot


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

    ball = obj.get("BallData") or {}
    club = obj.get("ClubData") or {}

    shot_number = obj.get("ShotNumber")
    if shot_number is not None:
        try:
            shot_number = int(shot_number)
        except (TypeError, ValueError):
            shot_number = None

    return Shot(
        captured_at=dbmod.now_iso(),
        device_id=obj.get("DeviceID"),
        shot_number=shot_number,
        ball_speed=_num(ball, "Speed"),
        total_spin=_num(ball, "TotalSpin"),
        spin_axis=_num(ball, "SpinAxis"),
        hla=_num(ball, "HLA"),
        vla=_num(ball, "VLA"),
        carry=_num(ball, "CarryDistance"),
        club_speed=_num(club, "Speed"),
        attack_angle=_num(club, "AngleOfAttack"),
        club_path=_num(club, "Path"),
        face_to_target=_num(club, "FaceToTarget"),
        raw_json=json.dumps(obj),
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_shotmap.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add catcher/shotmap.py catcher/tests/test_shotmap.py
git commit -m "feat(catcher): map GSPro Open Connect JSON to store Shot"
```

---

## Task 3: openconnect — GUI-agnostic listener (loopback test)

**Files:**
- Create: `catcher/openconnect.py`
- Create: `catcher/tests/test_openconnect.py`

- [ ] **Step 1: Write the failing test** (loopback fake-R50 client, incl. concatenated-JSON framing)

`catcher/tests/test_openconnect.py`:
```python
import json
import socket
import threading
import time

from catcher.openconnect import OpenConnectListener


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_listener_parses_newline_and_concatenated_json():
    received = []
    lock = threading.Lock()

    def on_message(obj, source):
        with lock:
            received.append(obj)

    port = _free_port()
    listener = OpenConnectListener(port=port, on_message=on_message,
                                   handedness="RH")
    listener.start()
    try:
        # wait for the server to be listening
        deadline = time.time() + 5.0
        while not listener.is_listening and time.time() < deadline:
            time.sleep(0.02)
        assert listener.is_listening

        # fake R50 dials the listener (like the real device connecting in)
        client = socket.create_connection(("127.0.0.1", port), timeout=5)
        client.settimeout(5)

        # server must send a 201 handshake on connect
        handshake = b""
        client.settimeout(5)
        while b"\n" not in handshake:
            handshake += client.recv(4096)
        first = json.loads(handshake.split(b"\n")[0].decode("utf-8"))
        assert first["Code"] == 201
        assert first["Player"]["Handed"] == "RH"

        # send TWO json objects concatenated with NO delimiter, plus a
        # newline-delimited third — exercises the tolerant stream parser.
        msg1 = {"ShotNumber": 1, "BallData": {"Speed": 100.0},
                "ShotDataOptions": {"IsHeartBeat": False}}
        msg2 = {"ShotNumber": 2, "BallData": {"Speed": 110.0},
                "ShotDataOptions": {"IsHeartBeat": False}}
        msg3 = {"ShotDataOptions": {"IsHeartBeat": True}}
        payload = (json.dumps(msg1) + json.dumps(msg2)
                   + json.dumps(msg3) + "\n").encode("utf-8")
        client.sendall(payload)

        # each inbound message is acked with a 200; read until we've seen 3 acks
        acks = 0
        buf = b""
        client.settimeout(5)
        deadline = time.time() + 5.0
        while acks < 3 and time.time() < deadline:
            try:
                data = client.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            buf += data
            acks = buf.count(b'"Code": 200') + buf.count(b'"Code":200')

        client.close()

        # the listener should have emitted all three parsed messages
        deadline = time.time() + 5.0
        while len(received) < 3 and time.time() < deadline:
            time.sleep(0.02)
        with lock:
            got = list(received)
        assert len(got) == 3
        assert got[0]["ShotNumber"] == 1
        assert got[1]["ShotNumber"] == 2
        assert got[2]["ShotDataOptions"]["IsHeartBeat"] is True
    finally:
        listener.stop()
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_openconnect.py -v`
Expected: FAIL (`catcher.openconnect` does not exist).

- [ ] **Step 3: Write the implementation** (server + probe + tolerant framing, lifted from the spike)

`catcher/openconnect.py`:
```python
"""GUI-agnostic GSPro Open Connect listener.

Pretends to be GSPro so a Garmin Approach R50 sends live shot data over the
GSPro Open Connect v1 protocol (TCP, JSON). Server listens on 0.0.0.0:<port>;
an optional probe dials the R50's IP so either connection direction works. On
connect it sends a 201 handshake (carrying the active player's handedness); it
acks every inbound message with a 200. The tolerant stream parser handles both
newline-delimited and concatenated JSON objects. Parsed messages are delivered
to on_message(obj, source); this module never touches the DB or tkinter.

Lifted from spike/gspro_spike_listener.py (_server_loop / _probe_loop /
_handle_conn / raw_decode framing), made reusable and callback-driven.
"""
import json
import socket
import threading
import time
from typing import Callable, Optional

PORT_DEFAULT = 921  # GSPro Open Connect default port


class OpenConnectListener:
    def __init__(self, port: int = PORT_DEFAULT,
                 on_message: Optional[Callable[[dict, str], None]] = None,
                 *, handedness: str = "RH", probe_ip: Optional[str] = None,
                 on_status: Optional[Callable[[str, str], None]] = None):
        self.port = port
        self.on_message = on_message or (lambda obj, source: None)
        self.handedness = handedness
        self.probe_ip = probe_ip
        self.on_status = on_status or (lambda kind, detail: None)

        self.running = False
        self.is_listening = False
        self._server_sock = None
        self._threads = []

    # ---- lifecycle --------------------------------------------------------
    def start(self):
        if self.running:
            return
        self.running = True
        t = threading.Thread(target=self._server_loop, daemon=True)
        t.start()
        self._threads.append(t)
        if self.probe_ip:
            pt = threading.Thread(target=self._probe_loop, daemon=True)
            pt.start()
            self._threads.append(pt)

    def stop(self):
        self.running = False
        try:
            if self._server_sock:
                self._server_sock.close()
        except OSError:
            pass
        self._server_sock = None
        self.is_listening = False

    def set_handedness(self, handedness: str):
        """Update handedness for the NEXT handshake (active-player switch)."""
        self.handedness = handedness

    # ---- protocol ---------------------------------------------------------
    def _send(self, sock, obj):
        try:
            sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
        except OSError:
            pass

    def _handle_conn(self, sock, source):
        self.on_status("connected", source)
        self._send(sock, {"Code": 201, "Message": "SUCCESS",
                          "Player": {"Handed": self.handedness, "Club": "DR"}})
        buf = ""
        dec = json.JSONDecoder()
        sock.settimeout(1.0)
        try:
            while self.running:
                try:
                    data = sock.recv(8192)
                except socket.timeout:
                    continue
                except OSError:
                    break
                if not data:
                    break
                buf += data.decode("utf-8", errors="replace")
                while True:
                    s = buf.lstrip()
                    if not s:
                        buf = ""
                        break
                    try:
                        obj, idx = dec.raw_decode(s)
                    except json.JSONDecodeError:
                        buf = s
                        break
                    buf = s[idx:]
                    try:
                        self.on_message(obj, source)
                    except Exception:
                        pass
                    self._send(sock, {"Code": 200, "Message": "OK"})
        finally:
            try:
                sock.close()
            except OSError:
                pass
            self.on_status("disconnected", source)

    def _server_loop(self):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", self.port))
            srv.listen(5)
            srv.settimeout(1.0)
            self._server_sock = srv
            self.is_listening = True
            self.on_status("listening", f"0.0.0.0:{self.port}")
        except OSError as e:
            self.on_status("bind_error", str(e))
            return
        while self.running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_conn,
                args=(conn, f"{addr[0]}:{addr[1]}"), daemon=True).start()
        try:
            srv.close()
        except OSError:
            pass
        self.is_listening = False

    def _probe_loop(self):
        target = self.probe_ip
        if not target:
            return
        while self.running:
            try:
                sock = socket.create_connection((target, self.port), timeout=3)
            except OSError:
                time.sleep(3)
                continue
            self._handle_conn(sock, f"PROBE->{target}:{self.port}")
            if self.running:
                time.sleep(3)
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_openconnect.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add catcher/openconnect.py catcher/tests/test_openconnect.py
git commit -m "feat(catcher): GUI-agnostic GSPro Open Connect listener with loopback test"
```

---

## Task 4: sessionmgr — active player + per-player auto session (brother↔you resume)

**Files:**
- Create: `catcher/sessionmgr.py`
- Create: `catcher/tests/test_sessionmgr.py`

- [ ] **Step 1: Write the failing test** (interleave two players within and beyond the idle window against the in-memory store)

`catcher/tests/test_sessionmgr.py`:
```python
from store import repo
from store.models import Shot
from catcher.sessionmgr import SessionManager


def _shot():
    # captured_at is overwritten by attribute(); player/session start empty
    return Shot(captured_at="placeholder", ball_speed=120.0)


def test_set_active_creates_player_and_tracks(db):
    mgr = SessionManager(db, idle_minutes=15)
    p = mgr.set_active_player("Chris", height_in=72.0, handedness="R")
    assert p.id is not None
    assert mgr.active_player.id == p.id


def test_attribute_opens_one_session_and_resumes_it(db):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    s1 = mgr.attribute(db, _shot())
    s2 = mgr.attribute(db, _shot())
    assert s1.player_id == mgr.active_player.id
    assert s1.session_id is not None
    # second shot for the same player resumes the same open session
    assert s2.session_id == s1.session_id


def test_brother_you_interleave_resumes_each_session(db):
    mgr = SessionManager(db, idle_minutes=15)

    # brother hits
    mgr.set_active_player("Brother", 70.0, "R")
    b1 = mgr.attribute(db, _shot())
    bro_session = b1.session_id
    bro_id = mgr.active_player.id

    # switch to you, you hit
    mgr.set_active_player("Chris", 72.0, "R")
    y1 = mgr.attribute(db, _shot())
    you_session = y1.session_id
    you_id = mgr.active_player.id

    # different player => different session, different player_id
    assert you_id != bro_id
    assert you_session != bro_session

    # switch back to brother within the idle window => his SAME session resumes
    mgr.set_active_player("Brother", 70.0, "R")
    b2 = mgr.attribute(db, _shot())
    assert b2.player_id == bro_id
    assert b2.session_id == bro_session

    # each person's shots stayed theirs
    bro_shots = db.execute(
        "SELECT player_id, session_id FROM shot WHERE player_id=?",
        (bro_id,)).fetchall()
    assert all(r["session_id"] == bro_session for r in bro_shots)
    assert len(bro_shots) == 2
    you_shots = db.execute(
        "SELECT session_id FROM shot WHERE player_id=?", (you_id,)).fetchall()
    assert len(you_shots) == 1 and you_shots[0]["session_id"] == you_session


def test_idle_timeout_starts_a_new_session(db):
    from datetime import datetime, timezone, timedelta
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    first = mgr.attribute(db, _shot())

    # backdate the saved shot to 30 minutes ago so the session looks idle
    old = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    db.execute("UPDATE shot SET captured_at=? WHERE id=?", (old, first.id))
    db.commit()

    # sweep idle sessions (what the periodic timer calls), then hit again
    closed = mgr.sweep_idle(db)
    assert closed == 1
    second = mgr.attribute(db, _shot())
    assert second.session_id != first.session_id  # a fresh session opened


def test_attribute_without_active_player_raises(db):
    mgr = SessionManager(db, idle_minutes=15)
    try:
        mgr.attribute(db, _shot())
        assert False, "expected an error when no active player is set"
    except RuntimeError:
        pass
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_sessionmgr.py -v`
Expected: FAIL (`catcher.sessionmgr` does not exist).

- [ ] **Step 3: Write the implementation**

The connection is captured at construction (`self._conn`) so `set_active_player`
can create/resolve players without the caller threading a connection through;
`attribute` / `sweep_idle` still take an explicit `conn` so the same manager can
be driven against the in-memory test store.

`catcher/sessionmgr.py`:
```python
"""Active-player state + per-player auto session resolution.

Holds which player is currently hitting. For each captured shot it stamps the
shot with the active player's id and the player's open session (resuming it if
one is open, else creating a new one). A periodic sweep closes sessions idle
longer than idle_minutes, so a player who returns within the window resumes the
same session, while a long gap starts a fresh one.

Uses store.repo exclusively. The connection captured at construction is used for
player lookups; attribute()/sweep_idle() take an explicit connection so the
manager works against an in-memory store in tests.
"""
from store import db as dbmod
from store import repo
from store.models import Shot


class SessionManager:
    def __init__(self, conn, idle_minutes: int = 15):
        self._conn = conn
        self.idle_minutes = idle_minutes
        self.active_player = None

    # ---- active player ----------------------------------------------------
    def set_active_player(self, name, height_in, handedness):
        """Select (creating if needed) the player who is now hitting."""
        self.active_player = repo.get_or_create_player(
            self._conn, name, height_in, handedness)
        return self.active_player

    def roster(self, conn=None):
        return repo.list_players(conn or self._conn)

    # ---- attribution ------------------------------------------------------
    def attribute(self, conn, shot: Shot) -> Shot:
        """Stamp shot.player_id + shot.session_id for the active player,
        opening or resuming the player's session. Refreshes captured_at.
        Persists nothing (persist.py saves)."""
        if self.active_player is None:
            raise RuntimeError("no active player selected")
        pid = self.active_player.id
        session = repo.get_open_session(conn, pid) or repo.create_session(conn, pid)
        shot.player_id = pid
        shot.session_id = session.id
        shot.captured_at = dbmod.now_iso()
        return shot

    def sweep_idle(self, conn) -> int:
        """Close sessions idle longer than idle_minutes. Returns count closed."""
        return repo.end_idle_sessions(conn, self.idle_minutes)
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_sessionmgr.py -v`
Expected: PASS (all 5 tests, incl. the brother↔you resume case).

- [ ] **Step 5: Commit**

```bash
git add catcher/sessionmgr.py catcher/tests/test_sessionmgr.py
git commit -m "feat(catcher): active-player session manager with per-player resume"
```

---

## Task 5: persist — save with buffer-on-failure + replay

**Files:**
- Create: `catcher/persist.py`
- Create: `catcher/tests/test_persist.py`

- [ ] **Step 1: Write the failing test** (failing store buffers to file; recovery replays + clears; nothing lost)

`catcher/tests/test_persist.py`:
```python
import json
import os

from store import repo
from store.models import Shot
from catcher.persist import ShotPersister


def _player_session(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    return pid, sid


def _shot(pid, sid, speed):
    return Shot(captured_at="2026-06-03T00:00:00+00:00", player_id=pid,
                session_id=sid, ball_speed=speed,
                raw_json=json.dumps({"BallData": {"Speed": speed}}))


def test_save_success_writes_to_store_and_no_buffer(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)
    saved = p.save(db, _shot(pid, sid, 100.0))
    assert saved.id is not None
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1
    assert not os.path.exists(tmp_buffer) or os.path.getsize(tmp_buffer) == 0
    assert p.pending_count() == 0


def test_save_failure_buffers_to_file(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)

    class BoomConn:
        def execute(self, *a, **k):
            raise RuntimeError("database is locked")

    # store raises => shot must be buffered, not lost, and not raised to caller
    result = p.save(BoomConn(), _shot(pid, sid, 142.0))
    assert result is None  # signals "buffered, not yet persisted"
    assert os.path.exists(tmp_buffer)
    lines = [l for l in open(tmp_buffer, encoding="utf-8").read().splitlines() if l]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["ball_speed"] == 142.0
    assert p.pending_count() == 1
    # DB itself untouched
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_replay_drains_buffer_into_recovered_store(db, tmp_buffer):
    pid, sid = _player_session(db)
    p = ShotPersister(buffer_path=tmp_buffer)

    class BoomConn:
        def execute(self, *a, **k):
            raise RuntimeError("database is locked")

    p.save(BoomConn(), _shot(pid, sid, 101.0))
    p.save(BoomConn(), _shot(pid, sid, 102.0))
    assert p.pending_count() == 2

    # DB recovers: replay drains the buffer into the real store
    replayed = p.replay(db)
    assert replayed == 2
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 2
    speeds = sorted(r["ball_speed"] for r in
                    db.execute("SELECT ball_speed FROM shot").fetchall())
    assert speeds == [101.0, 102.0]
    # buffer cleared after successful replay
    assert p.pending_count() == 0
    assert not os.path.exists(tmp_buffer) or os.path.getsize(tmp_buffer) == 0


def test_replay_with_empty_buffer_is_noop(db, tmp_buffer):
    p = ShotPersister(buffer_path=tmp_buffer)
    assert p.replay(db) == 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_persist.py -v`
Expected: FAIL (`catcher.persist` does not exist).

- [ ] **Step 3: Write the implementation**

`catcher/persist.py`:
```python
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
    "club_speed", "attack_angle", "club_path", "face_to_target", "raw_json",
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
```

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_persist.py -v`
Expected: PASS (all 4 tests).

- [ ] **Step 5: Commit**

```bash
git add catcher/persist.py catcher/tests/test_persist.py
git commit -m "feat(catcher): buffer-on-failure shot persistence with replay"
```

---

## Task 6: app — wire listener → shotmap → sessionmgr → persist + tkinter wizard

**Files:**
- Create: `catcher/app.py`
- Create: `catcher/run.py`
- Create: `catcher/tests/test_app.py`

This task assembles the pieces into the tkinter app grown from the spike wizard.
The GUI keeps the spike's connect flow and live status, and adds: a "Who's
hitting?" active-player switch, an "Add player" form (name / height / handedness),
a live shot feed, and a session/connection status line. To keep it testable, the
ingest pipeline lives in a GUI-free `ShotPipeline` that the app drives; the
construction smoke test exercises `--selftest` like the spike.

- [ ] **Step 1: Write the failing test** (headless pipeline behaviour + `--selftest` construction smoke test)

`catcher/tests/test_app.py`:
```python
import os
import subprocess
import sys

from store import repo
from catcher.app import ShotPipeline
from catcher.sessionmgr import SessionManager
from catcher.persist import ShotPersister


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_pipeline_persists_shot_for_active_player(db, tmp_buffer):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    persister = ShotPersister(buffer_path=tmp_buffer)
    pipeline = ShotPipeline(db, mgr, persister)

    msg = {"DeviceID": "R50", "ShotNumber": 1,
           "BallData": {"Speed": 148.0, "VLA": 13.0, "TotalSpin": 2700.0},
           "ShotDataOptions": {"IsHeartBeat": False}}
    saved = pipeline.handle(msg, source="test")
    assert saved is not None
    assert saved.player_id == mgr.active_player.id
    assert saved.session_id is not None
    assert saved.ball_speed == 148.0
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 1


def test_pipeline_ignores_heartbeat(db, tmp_buffer):
    mgr = SessionManager(db, idle_minutes=15)
    mgr.set_active_player("Chris", 72.0, "R")
    pipeline = ShotPipeline(db, mgr, ShotPersister(buffer_path=tmp_buffer))
    out = pipeline.handle({"ShotDataOptions": {"IsHeartBeat": True}}, source="t")
    assert out is None
    assert db.execute("SELECT COUNT(*) c FROM shot").fetchone()["c"] == 0


def test_pipeline_buffers_when_no_active_player(db, tmp_buffer):
    # a shot arriving before anyone is selected must not be lost: it buffers
    mgr = SessionManager(db, idle_minutes=15)
    pipeline = ShotPipeline(db, mgr, ShotPersister(buffer_path=tmp_buffer))
    out = pipeline.handle(
        {"DeviceID": "R50", "ShotNumber": 1,
         "BallData": {"Speed": 99.0},
         "ShotDataOptions": {"IsHeartBeat": False}}, source="t")
    assert out is None
    assert os.path.exists(tmp_buffer)
    assert pipeline.persister.pending_count() == 1


def test_selftest_constructs_headlessly():
    # tkinter ships with Python; --selftest builds the window and tears it down
    result = subprocess.run(
        [sys.executable, "-m", "catcher.run", "--selftest"],
        cwd=REPO_ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert "selftest ok" in result.stdout
```

- [ ] **Step 2: Run to verify it fails**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_app.py -v`
Expected: FAIL (`catcher.app` / `catcher.run` do not exist).

- [ ] **Step 3: Write the pipeline + app**

`catcher/app.py`:
```python
"""Tkinter shot catcher grown from the spike wizard, plus a GUI-free pipeline.

ShotPipeline is the testable core: it maps a raw GSPro message to a Shot,
attributes it to the active player + session, and persists it (buffering on
failure). If no player is selected yet, the shot is buffered rather than lost.

CatcherApp is the tkinter UI: connect flow + live capture, a "Who's hitting?"
active-player switch, an Add-player form, a live shot feed, and session/
connection status. It runs the OpenConnectListener on a background thread and
marshals events to the UI thread via a queue (like the spike).
"""
import queue

from catcher import shotmap
from catcher.openconnect import OpenConnectListener, PORT_DEFAULT
from catcher.persist import ShotPersister
from catcher.sessionmgr import SessionManager

# ---- palette / fonts (carried from the spike) ------------------------------
BG = "#eef1f5"
CARD = "#ffffff"
INK = "#16202b"
SUB = "#5d6b7a"
GREEN = "#1a8f4a"
GREEN_BG = "#e4f7ec"
AMBER = "#9a6a06"
AMBER_BG = "#fdf3da"
RED = "#b5302a"
RED_BG = "#fbe7e5"
ACCENT = "#0a66c2"
LINE = "#d7dde4"
FONT = "Segoe UI"


def F(size, bold=False):
    return (FONT, size, "bold" if bold else "normal")


# ============================ GUI-free pipeline =============================

class ShotPipeline:
    """Raw GSPro message -> Shot -> attributed -> persisted. Returns the saved
    Shot, or None for heartbeats / buffered shots. Never raises on DB errors."""

    def __init__(self, conn, session_mgr: SessionManager, persister: ShotPersister):
        self.conn = conn
        self.session_mgr = session_mgr
        self.persister = persister

    def handle(self, obj: dict, source: str = ""):
        shot = shotmap.map_message(obj)
        if shot is None:
            return None  # heartbeat
        if self.session_mgr.active_player is None:
            # no one selected yet: don't lose it, buffer the raw shot
            self.persister._buffer(shot)
            return None
        self.session_mgr.attribute(self.conn, shot)
        return self.persister.save(self.conn, shot)


# ============================ tkinter app ===================================

class CatcherApp:
    def __init__(self, root, conn, *, port=PORT_DEFAULT, idle_minutes=15,
                 probe_ip=None, buffer_path=None):
        import tkinter as tk
        from tkinter import ttk
        self.tk = tk
        self.ttk = ttk
        self.root = root
        self.conn = conn
        self.q = queue.Queue()

        self.session_mgr = SessionManager(conn, idle_minutes=idle_minutes)
        self.persister = ShotPersister(buffer_path=buffer_path)
        self.pipeline = ShotPipeline(conn, self.session_mgr, self.persister)

        self.shot_count = 0
        self.connected = False
        self.listener = OpenConnectListener(
            port=port,
            on_message=self._on_listener_message,
            handedness="RH",
            probe_ip=probe_ip,
            on_status=self._on_listener_status,
        )

        self._build_ui()
        self.root.after(100, self._drain_queue)
        self.root.after(5000, self._tick_idle)
        self.root.after(7000, self._tick_replay)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.listener.start()
        self._refresh_roster()

    # ---- listener callbacks (background thread) ---------------------------
    def _on_listener_message(self, obj, source):
        self.q.put(("message", (obj, source)))

    def _on_listener_status(self, kind, detail):
        self.q.put(("status", (kind, detail)))

    # ---- UI build ---------------------------------------------------------
    def _build_ui(self):
        tk, ttk = self.tk, self.ttk
        self.root.title("Golf Shot Catcher")
        self.root.configure(bg=BG)
        self.root.geometry("880x700")
        self.root.minsize(780, 620)

        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(header, text="\U0001F3CC  Golf Shot Catcher", bg=BG, fg=INK,
                 font=F(17, True)).pack(side="left")
        self.status_lbl = tk.Label(header, text="Starting up…", bg=BG,
                                    fg=AMBER, font=F(11, True))
        self.status_lbl.pack(side="right")

        # who's hitting
        who = tk.LabelFrame(self.root, text="Who's hitting?", bg=CARD, fg=INK,
                            font=F(12, True))
        who.pack(fill="x", padx=24, pady=8)
        self.roster_frame = tk.Frame(who, bg=CARD)
        self.roster_frame.pack(fill="x", padx=12, pady=8)
        self.active_lbl = tk.Label(who, text="Active: (nobody yet)", bg=CARD,
                                   fg=GREEN, font=F(12, True))
        self.active_lbl.pack(anchor="w", padx=12, pady=(0, 8))

        # add player
        add = tk.Frame(who, bg=CARD)
        add.pack(fill="x", padx=12, pady=(0, 10))
        self.name_var = tk.StringVar()
        self.height_var = tk.StringVar(value="70")
        self.hand_var = tk.StringVar(value="R")
        tk.Label(add, text="Name", bg=CARD, fg=SUB, font=F(10)).pack(side="left")
        tk.Entry(add, textvariable=self.name_var, width=14).pack(side="left", padx=4)
        tk.Label(add, text="Height (in)", bg=CARD, fg=SUB, font=F(10)).pack(side="left")
        tk.Entry(add, textvariable=self.height_var, width=5).pack(side="left", padx=4)
        tk.Label(add, text="Hand", bg=CARD, fg=SUB, font=F(10)).pack(side="left")
        ttk.Combobox(add, textvariable=self.hand_var, width=3, state="readonly",
                     values=["R", "L"]).pack(side="left", padx=4)
        tk.Button(add, text="Add / select", command=self._add_player, bg=ACCENT,
                  fg="white", font=F(10, True), relief="flat", padx=12,
                  cursor="hand2").pack(side="left", padx=8)

        # live shot feed
        feed = tk.LabelFrame(self.root, text="Live shots", bg=CARD, fg=INK,
                             font=F(12, True))
        feed.pack(fill="both", expand=True, padx=24, pady=8)
        cols = ("time", "player", "ballspd", "vla", "spin", "carry", "club")
        heads = ("Time", "Player", "BallSpd", "VLA", "Spin", "Carry", "Club?")
        self.tree = ttk.Treeview(feed, columns=cols, show="headings", height=10)
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=90, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(feed, orient="vertical", command=self.tree.yview)
        sb.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=sb.set)

        # footer status
        self.footer = tk.Label(self.root, text="Session: —    Shots: 0",
                               bg=BG, fg=SUB, font=F(10, True))
        self.footer.pack(fill="x", padx=24, pady=(0, 12))

    # ---- roster / active player -------------------------------------------
    def _refresh_roster(self):
        for w in self.roster_frame.winfo_children():
            w.destroy()
        for p in self.session_mgr.roster(self.conn):
            self.tk.Button(
                self.roster_frame, text=p.name,
                command=lambda pl=p: self._select_existing(pl),
                bg="#dfe5ec", fg=INK, font=F(10, True), relief="flat",
                padx=10, pady=4, cursor="hand2").pack(side="left", padx=4)

    def _select_existing(self, player):
        self.session_mgr.set_active_player(
            player.name, player.height_in, player.handedness)
        self.listener.set_handedness("LH" if player.handedness == "L" else "RH")
        self.active_lbl.configure(text=f"Active: {player.name}")

    def _add_player(self):
        name = self.name_var.get().strip()
        if not name:
            return
        try:
            height = float(self.height_var.get())
        except ValueError:
            height = 70.0
        hand = self.hand_var.get() or "R"
        self.session_mgr.set_active_player(name, height, hand)
        self.listener.set_handedness("LH" if hand == "L" else "RH")
        self.active_lbl.configure(text=f"Active: {name}")
        self.name_var.set("")
        self._refresh_roster()

    # ---- queue pump -------------------------------------------------------
    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "status":
                    self._apply_status(*payload)
                elif kind == "message":
                    self._apply_message(*payload)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _apply_status(self, kind, detail):
        if kind == "listening":
            self.status_lbl.configure(text="Waiting for your R50…", fg=AMBER)
        elif kind == "connected":
            self.connected = True
            self.status_lbl.configure(text="Connected to your R50", fg=GREEN)
        elif kind == "disconnected":
            self.connected = False
            self.status_lbl.configure(text="Waiting for your R50…", fg=AMBER)
        elif kind == "bind_error":
            self.status_lbl.configure(
                text="Port 921 in use — close GSPro", fg=RED)

    def _apply_message(self, obj, source):
        saved = self.pipeline.handle(obj, source)
        if saved is None:
            return  # heartbeat or buffered-without-player
        self.shot_count += 1
        player = self.session_mgr.active_player
        club = "yes" if saved.club_speed is not None else "no"
        self.tree.insert("", "end", values=(
            saved.captured_at[11:19], player.name if player else "?",
            _fmt(saved.ball_speed), _fmt(saved.vla),
            _fmt(saved.total_spin), _fmt(saved.carry), club))
        self.tree.yview_moveto(1.0)
        self.footer.configure(
            text=f"Session: {saved.session_id}    Shots: {self.shot_count}")

    # ---- periodic timers --------------------------------------------------
    def _tick_idle(self):
        try:
            self.session_mgr.sweep_idle(self.conn)
        except Exception:
            pass
        self.root.after(60000, self._tick_idle)  # every minute

    def _tick_replay(self):
        try:
            if self.persister.pending_count():
                self.persister.replay(self.conn)
        except Exception:
            pass
        self.root.after(10000, self._tick_replay)  # every 10s

    def _on_close(self):
        try:
            self.listener.stop()
        finally:
            self.root.destroy()


def _fmt(v):
    if v is None:
        return "—"
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)
```

`catcher/run.py`:
```python
"""Entry point for the R50 shot catcher. Packaged to a standalone exe.

  python -m catcher.run                 # launch the catcher
  python -m catcher.run --selftest      # build + tear down the window, headless
"""
import argparse
import sys

from store import db as dbmod
from catcher.openconnect import PORT_DEFAULT


def build_args(argv=None):
    ap = argparse.ArgumentParser(description="GarageTEC R50 shot catcher")
    ap.add_argument("--port", type=int, default=PORT_DEFAULT)
    ap.add_argument("--idle-minutes", type=int, default=15)
    ap.add_argument("--db", default=None,
                    help="SQLite path (default: store's default DB)")
    ap.add_argument("--probe-ip", default=None,
                    help="R50 IP to dial (default: listen only)")
    ap.add_argument("--selftest", action="store_true",
                    help="construct the window headlessly and exit")
    return ap.parse_args(argv)


def main(argv=None):
    args = build_args(argv)
    import tkinter as tk
    from catcher.app import CatcherApp

    conn = dbmod.init_db(path=args.db)

    if args.selftest:
        root = tk.Tk()
        app = CatcherApp(root, conn, port=args.port,
                         idle_minutes=args.idle_minutes, probe_ip=args.probe_ip)
        root.update()        # build + render once
        app.listener.stop()  # stop the listener thread explicitly
        root.destroy()       # tear the window down
        print("selftest ok")
        return 0

    root = tk.Tk()
    CatcherApp(root, conn, port=args.port, idle_minutes=args.idle_minutes,
               probe_ip=args.probe_ip)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

> Why `--selftest` is robust to port 921 being busy: a `bind_error` is reported
> via the status queue (not raised), so the window still constructs even if GSPro
> or another catcher already holds the port. The selftest stops the listener
> explicitly and `daemon=True` threads exit with the process, so the subprocess
> exits cleanly with `selftest ok`.

- [ ] **Step 4: Run to verify it passes**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/tests/test_app.py -v`
Expected: PASS (all 4 tests, incl. the `--selftest` subprocess smoke test).

> If the `--selftest` subprocess test fails with a tkinter "no display" error,
> the machine has no GUI available; on this Windows target tkinter is present, so
> it should construct. Do not stub tkinter — keep the real construction test.

- [ ] **Step 5: Run the whole catcher suite**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/ -v`
Expected: PASS (shotmap, openconnect, sessionmgr, persist, app all green).

- [ ] **Step 6: Commit**

```bash
git add catcher/app.py catcher/run.py catcher/tests/test_app.py
git commit -m "feat(catcher): wire pipeline + tkinter wizard with --selftest"
```

---

## Task 7: Ignore the runtime buffer + DB artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Ensure the runtime buffer and local DB are not committed**

Append to `.gitignore` (create the file if it does not exist; do not duplicate
lines already present):
```
data/pending_shots.jsonl
data/*.db
data/*.db-wal
data/*.db-shm
```

- [ ] **Step 2: Confirm nothing stray is staged**

Run: `git status --short`
Expected: only `.gitignore` shows as modified (no `data/` artifacts listed).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore(catcher): gitignore pending-shots buffer and local db"
```

---

## Task 8: Package to a standalone exe (PyInstaller, like the spike)

**Files:**
- Create: `catcher/build_exe.md` (build runbook — a doc, not code)

This mirrors how the spike was packaged. PyInstaller is a build-time tool only;
it is not a runtime dependency and is not added to `requirements-dev.txt`.

- [ ] **Step 1: Install PyInstaller (build host only)**

Run: `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install pyinstaller`
Expected: `Successfully installed pyinstaller-...`

- [ ] **Step 2: Build the one-file exe**

Run (from the repo root `C:\Users\chris\Documents\Golf`):
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller --onefile --windowed --name GolfShotCatcher --collect-submodules store --collect-data store catcher/run.py
```
Expected: `dist\GolfShotCatcher.exe` is produced. `--collect-data store` bundles
`store/schema.sql` so `init_db` works inside the frozen exe.

- [ ] **Step 3: Smoke-test the exe headlessly**

Run: `dist\GolfShotCatcher.exe --selftest`
Expected: process exits 0 and prints `selftest ok` (window builds + tears down).

> Note: the frozen exe writes its DB + `pending_shots.jsonl` under the store's
> default `data/` directory. To redirect, run with `--db <path>` or set the
> `GARAGETEC_DATA_DIR` environment variable (honoured by `store.db.default_db_path`).

- [ ] **Step 4: Write the build runbook doc**

`catcher/build_exe.md`:
```markdown
# Building GolfShotCatcher.exe

PyInstaller is a build-time tool only (not a runtime/dev dependency).

## One-time
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pip install pyinstaller
```

## Build (from repo root)
```
C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m PyInstaller ^
  --onefile --windowed --name GolfShotCatcher ^
  --collect-submodules store --collect-data store ^
  catcher/run.py
```
Output: `dist\GolfShotCatcher.exe`.

`--collect-data store` bundles `store/schema.sql` so `init_db` works inside the
frozen exe.

## Verify
```
dist\GolfShotCatcher.exe --selftest      # prints "selftest ok", exits 0
```

## Runtime data location
The exe writes `garagetec.db` + `pending_shots.jsonl` under the store's default
`data/` directory. Override with `--db <path>` or the `GARAGETEC_DATA_DIR`
environment variable.

## Windows Firewall
On first run Windows may prompt to allow the app on the network (it listens on
TCP 921). Click **Allow**.
```

- [ ] **Step 5: Commit the runbook (the `dist/` and `build/` outputs are not committed)**

Add `dist/` and `build/` and `*.spec` to `.gitignore` if not already ignored,
then:
```bash
git add catcher/build_exe.md .gitignore
git commit -m "docs(catcher): PyInstaller build runbook for standalone exe"
```

---

## Done criteria

- `C:\Users\chris\AppData\Local\Programs\Python\Python312\python.exe -m pytest catcher/ -v` is fully green.
- `catcher/` provides: a reusable `OpenConnectListener` (loopback-tested, tolerant framing), a pure `shotmap.map_message`, a `SessionManager` with verified brother↔you resume, a `ShotPersister` with buffer-on-failure + replay, and a tkinter `CatcherApp` that constructs headlessly via `--selftest`.
- Every shot is persisted or buffered (never lost), attributed to the active player + an auto-resuming per-player session.
- No new runtime dependency beyond the stdlib + the `store/` package; PyInstaller is build-only.
- `data/pending_shots.jsonl`, the local DB, and PyInstaller outputs are gitignored.
```
