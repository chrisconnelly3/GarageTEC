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
        self._conns = []        # live sockets, for mid-connection Player pushes
        self.club = "DR"        # GSPro club code most recently pushed

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

    # ---- protocol ---------------------------------------------------------
    def _send(self, sock, obj):
        try:
            sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
        except OSError:
            pass

    def _handle_conn(self, sock, source):
        self.on_status("connected", source)
        self._conns.append(sock)
        self._send(sock, {"Code": 201, "Message": "SUCCESS",
                          "Player": {"Handed": self.handedness,
                                     "Club": self.club}})
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
                self._conns.remove(sock)
            except ValueError:
                pass
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
