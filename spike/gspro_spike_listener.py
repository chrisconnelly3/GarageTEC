"""
R50 GSPro Open Connect - Spike Listener  (friendly wizard edition)
------------------------------------------------------------------
Pretends to be GSPro so a Garmin Approach R50 will send it live shot data over
the documented GSPro Open Connect v1 protocol (TCP, JSON). Goal of the spike:
prove we can capture R50 shots with a homemade "direct listener", and see which
fields (ball / club) the R50 sends.

This edition is built for a non-technical user: the engine auto-starts and the
UI is a guided, plain-language, 3-step wizard. All technical controls live in a
"Technical details" window so no functionality is lost.

Pure Python standard library only (tkinter ships with the python.org build).
"""

import socket
import threading
import json
import queue
import time
import os
import sys
from datetime import datetime

import tkinter as tk
from tkinter import ttk

PORT_DEFAULT = 921  # GSPro Open Connect default port

# ---- palette / fonts -------------------------------------------------------
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
ACCENT_DK = "#08518f"
LINE = "#d7dde4"
FONT = "Segoe UI"


def F(size, bold=False):
    return (FONT, size, "bold" if bold else "normal")


# ----------------------------- helpers --------------------------------------

def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def now_str():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def get_primary_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


def get_all_ips():
    ips = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            ip = info[4][0]
            if ":" not in ip:
                ips.add(ip)
    except Exception:
        pass
    ips.add(get_primary_ip())
    return sorted(ips)


def guess_gateway(ip):
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3] + ["1"])
    return ip


def fmt(v):
    if v is None:
        return ""
    try:
        return f"{float(v):.2f}"
    except Exception:
        return str(v)


def rint(v):
    if v is None:
        return "--"
    try:
        return str(int(round(float(v))))
    except Exception:
        return str(v)


# ============================ the app =======================================

class App:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()

        # engine state
        self.running = False
        self.server_sock = None
        self.logfile = None
        self.logpath = None
        self.file_lock = threading.Lock()
        self.msg_count = 0
        self.shot_count = 0
        self.hb_count = 0
        self.connected = False

        # ui state
        self.current_step = 0
        self.initial_ip = get_primary_ip()
        self.last_ip = self.initial_ip
        self.addr_var = tk.StringVar(value=self.initial_ip)
        self.hint_var = tk.StringVar(value="")
        self.shots_buffer = []   # rows for the technical table
        self.log_buffer = []     # lines for the technical raw log
        self.adv = None          # technical-details window (Toplevel) or None

        self._build_ui()
        self.root.after(100, self._drain_queue)
        self.root.after(1500, self._poll_network)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(500, self.start_engine)  # auto-start, no button needed

    # --------------------------- UI scaffold --------------------------------
    def _build_ui(self):
        self.root.title("Golf Shot Capture")
        self.root.configure(bg=BG)
        self.root.geometry("860x680")
        self.root.minsize(760, 600)
        try:
            ttk.Style().theme_use("vista")
        except Exception:
            pass

        # ---- header
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=24, pady=(18, 6))
        tk.Label(header, text="\U0001F3CC  Golf Shot Capture", bg=BG, fg=INK,
                 font=F(17, True)).pack(side="left")
        self.dots_frame = tk.Frame(header, bg=BG)
        self.dots_frame.pack(side="right")
        self.dot_lbls = []
        for i in range(3):
            d = tk.Label(self.dots_frame, text="●", bg=BG, fg=LINE, font=F(14))
            d.pack(side="left", padx=3)
            self.dot_lbls.append(d)

        # ---- error banner (hidden unless needed)
        self.err_banner = tk.Frame(self.root, bg=RED_BG)
        self.err_text = tk.Label(self.err_banner, text="", bg=RED_BG, fg=RED,
                                 font=F(11, True), justify="left", wraplength=720)
        self.err_text.pack(side="left", padx=14, pady=10)
        tk.Button(self.err_banner, text="Try again", command=self.restart_engine,
                  bg=RED, fg="white", font=F(10, True), relief="flat",
                  padx=14, pady=6, bd=0, cursor="hand2").pack(side="right", padx=12)

        # ---- card (content)
        self.card = tk.Frame(self.root, bg=CARD, highlightbackground=LINE,
                             highlightthickness=1)
        self.card.pack(fill="both", expand=True, padx=24, pady=10)

        self.content = tk.Frame(self.card, bg=CARD)
        self.content.pack(fill="both", expand=True, padx=30, pady=24)

        # ---- nav row
        nav = tk.Frame(self.card, bg=CARD)
        nav.pack(fill="x", side="bottom", padx=30, pady=(0, 20))
        self.btn_back = tk.Button(nav, text="◀  Back", command=self._go_back,
                                  bg=CARD, fg=SUB, font=F(11), relief="flat", bd=0,
                                  activebackground=CARD, cursor="hand2")
        self.btn_back.pack(side="left")
        self.btn_next = tk.Button(nav, text="Next  ▶", command=self._go_next,
                                  bg=ACCENT, fg="white", font=F(12, True),
                                  relief="flat", bd=0, padx=22, pady=10,
                                  activebackground=ACCENT_DK,
                                  activeforeground="white", cursor="hand2")
        self.btn_next.pack(side="right")

        # ---- footer (status chip + links) always visible
        footer = tk.Frame(self.root, bg=BG)
        footer.pack(fill="x", padx=24, pady=(0, 16))
        chip = tk.Frame(footer, bg=AMBER_BG)
        chip.pack(side="left")
        self.chip_dot = tk.Label(chip, text="●", bg=AMBER_BG, fg=AMBER, font=F(11))
        self.chip_dot.pack(side="left", padx=(10, 4), pady=5)
        self.chip_text = tk.Label(chip, text="Starting up...", bg=AMBER_BG, fg=AMBER,
                                  font=F(10, True))
        self.chip_text.pack(side="left", padx=(0, 12), pady=5)
        self.chip = chip

        links = tk.Frame(footer, bg=BG)
        links.pack(side="right")
        for txt, cmd in (("Help", self.show_help),
                         ("Technical details", self.open_advanced),
                         ("Start over", self._restart_wizard)):
            tk.Button(links, text=txt, command=cmd, bg=BG, fg=SUB, font=F(9),
                      relief="flat", bd=0, activebackground=BG, cursor="hand2"
                      ).pack(side="left", padx=8)

        # build the step frames
        self.frames = [self._make_welcome(), self._make_step1(),
                       self._make_step2(), self._make_step3()]
        self.show_step(0)

    # --------------------------- step builders ------------------------------
    def _new_frame(self):
        return tk.Frame(self.content, bg=CARD)

    def _heading(self, parent, text):
        tk.Label(parent, text=text, bg=CARD, fg=INK, font=F(16, True),
                 justify="left", anchor="w").pack(fill="x", pady=(0, 14))

    def _body(self, parent, text, fg=INK, size=12, pady=4):
        tk.Label(parent, text=text, bg=CARD, fg=fg, font=F(size),
                 justify="left", anchor="w", wraplength=720).pack(fill="x", pady=pady)

    def _note(self, parent, text, fg=AMBER, bg=AMBER_BG):
        box = tk.Frame(parent, bg=bg)
        box.pack(fill="x", pady=12)
        tk.Label(box, text=text, bg=bg, fg=fg, font=F(11), justify="left",
                 wraplength=700, anchor="w").pack(fill="x", padx=14, pady=10)

    def _addr_box(self, parent):
        """The 'only if it asks for an address' fallback, de-emphasized."""
        box = tk.Frame(parent, bg="#f3f5f8", highlightbackground=LINE,
                       highlightthickness=1)
        box.pack(fill="x", pady=(16, 4))
        tk.Label(box, text="Only if your R50 asks you to type an “address” or "
                 "“host”:", bg="#f3f5f8", fg=SUB, font=F(9),
                 justify="left", anchor="w").pack(fill="x", padx=12, pady=(8, 2))
        row = tk.Frame(box, bg="#f3f5f8")
        row.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(row, textvariable=self.addr_var, bg="#f3f5f8", fg=INK,
                 font=("Consolas", 13, "bold")).pack(side="left")
        tk.Label(row, text="   Port: 921", bg="#f3f5f8", fg=SUB,
                 font=("Consolas", 11)).pack(side="left")
        tk.Button(row, text="Copy", command=self._copy_addr, bg="#dfe5ec", fg=INK,
                  font=F(9, True), relief="flat", bd=0, padx=12, pady=3,
                  cursor="hand2").pack(side="right")

    def _make_welcome(self):
        fr = self._new_frame()
        self._heading(fr, "Let’s capture some golf shots")
        self._body(fr, "This little app listens to your Garmin R50 and shows each "
                       "shot as you hit it, so we can confirm the data comes "
                       "through. Setup takes about 2 minutes — I’ll walk you "
                       "through 3 short steps.")
        self._note(fr, "Heads up: the first time, Windows might ask to “allow” "
                       "this app on your network. Click Allow / Yes. (If you saw a "
                       "blue “Windows protected your PC” box earlier, you "
                       "already handled it by clicking Run anyway. \U0001F44D)")
        self._body(fr, "When you’re ready, click the blue button below.", fg=SUB, size=11)
        return fr

    def _make_step1(self):
        fr = self._new_frame()
        self._heading(fr, "Step 1 of 3 · Get your R50 ready")
        for line in (
            "1.   Turn on your Garmin R50.",
            "2.   On the R50’s screen, tap   Connect.",
            "3.   Tap   GSPro   from the list of options.",
            "4.   The R50 will show a Wi-Fi name and a password.",
            "        Leave that screen up — you’ll need it in the next step.",
        ):
            self._body(fr, line, size=13, pady=5)
        self._body(fr, "(“GSPro” is just one of the connection choices on the "
                       "R50. We’re borrowing it to grab the shot data.)",
                   fg=SUB, size=10, pady=(14))
        return fr

    def _make_step2(self):
        fr = self._new_frame()
        self._heading(fr, "Step 2 of 3 · Connect this computer to the R50")
        self._body(fr, "Your R50 is now broadcasting its own Wi-Fi. Let’s connect "
                       "this computer to it:", size=12)
        for line in (
            "1.   Click the Wi-Fi icon at the bottom-right of this screen (near the clock).",
            "2.   Find the Wi-Fi name that’s shown on your R50’s screen.",
            "3.   Click it, type the password from the R50, and click Connect.",
        ):
            self._body(fr, line, size=13, pady=5)
        self._body(fr, "Don’t worry — you’ll still have internet.", fg=SUB,
                   size=11, pady=(8))
        self.hint_lbl = tk.Label(fr, textvariable=self.hint_var, bg=CARD, fg=GREEN,
                                 font=F(12, True), justify="left", anchor="w",
                                 wraplength=720)
        self.hint_lbl.pack(fill="x", pady=(6, 0))
        self._addr_box(fr)
        return fr

    def _make_step3(self):
        fr = self._new_frame()
        self._heading(fr, "Step 3 of 3 · Take a swing!")
        self._body(fr, "On the R50, it should now connect to GSPro automatically "
                       "(give it a few seconds). Then just hit a shot.", size=12)

        # big live status
        self.live_box = tk.Frame(fr, bg=AMBER_BG)
        self.live_box.pack(fill="x", pady=(14, 8))
        self.live_dot = tk.Label(self.live_box, text="●", bg=AMBER_BG, fg=AMBER,
                                 font=F(20))
        self.live_dot.pack(side="left", padx=(16, 8), pady=14)
        livetxt = tk.Frame(self.live_box, bg=AMBER_BG)
        livetxt.pack(side="left", fill="x", expand=True, pady=12)
        self.live_status = tk.Label(livetxt, text="Waiting for your R50…", bg=AMBER_BG,
                                    fg=AMBER, font=F(16, True), anchor="w")
        self.live_status.pack(fill="x")
        self.live_sub = tk.Label(livetxt, text="(make sure you finished Step 2)",
                                 bg=AMBER_BG, fg=AMBER, font=F(10), anchor="w")
        self.live_sub.pack(fill="x")

        # last shot details
        self.shot_big = tk.Label(fr, text="", bg=CARD, fg=GREEN, font=F(15, True),
                                 justify="left", anchor="w")
        self.shot_big.pack(fill="x", pady=(6, 0))
        self.shot_detail = tk.Label(fr, text="", bg=CARD, fg=INK, font=("Consolas", 12),
                                    justify="left", anchor="w")
        self.shot_detail.pack(fill="x", pady=2)
        self.shot_club = tk.Label(fr, text="", bg=CARD, fg=SUB, font=F(11),
                                  justify="left", anchor="w")
        self.shot_club.pack(fill="x")
        self.shot_total_lbl = tk.Label(fr, text="", bg=CARD, fg=SUB, font=F(11, True),
                                       justify="left", anchor="w")
        self.shot_total_lbl.pack(fill="x", pady=(8, 0))

        self._addr_box(fr)
        return fr

    # --------------------------- navigation ---------------------------------
    def show_step(self, n):
        n = max(0, min(3, n))
        self.current_step = n
        for fr in self.frames:
            fr.pack_forget()
        self.frames[n].pack(fill="both", expand=True)

        # progress dots (welcome shows none lit)
        for i, d in enumerate(self.dot_lbls):
            lit = (n >= 1 and i <= n - 1)
            d.configure(fg=ACCENT if lit else LINE)

        # nav buttons
        if n == 0:
            self.btn_back.pack_forget()
            self.btn_next.configure(text="Let’s go  ▶", command=self._go_next)
        elif n == 3:
            self.btn_back.pack(side="left")
            self.btn_next.configure(text="✅  All done — get the file to send",
                                    command=self.finish_and_open)
        else:
            self.btn_back.pack(side="left")
            self.btn_next.configure(text="Next  ▶", command=self._go_next)

    def _go_next(self):
        self.show_step(self.current_step + 1)

    def _go_back(self):
        self.show_step(self.current_step - 1)

    def _restart_wizard(self):
        self.show_step(0)

    def _copy_addr(self):
        try:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.addr_var.get())
        except Exception:
            pass

    # --------------------------- status painting ----------------------------
    def _paint(self, where_dot, where_text, color, bg, dot_txt="●"):
        where_dot.configure(fg=color, bg=bg, text=dot_txt)
        where_text.configure(fg=color, bg=bg)

    def _set_state(self, state, msg=None):
        if state == "starting":
            self.chip.configure(bg=AMBER_BG)
            self._paint(self.chip_dot, self.chip_text, AMBER, AMBER_BG)
            self.chip_text.configure(text="Starting up…")
        elif state == "waiting":
            self.chip.configure(bg=AMBER_BG)
            self._paint(self.chip_dot, self.chip_text, AMBER, AMBER_BG)
            self.chip_text.configure(text="Waiting for your R50…")
            self.live_box.configure(bg=AMBER_BG)
            self.live_dot.configure(bg=AMBER_BG, fg=AMBER)
            self.live_status.configure(bg=AMBER_BG, fg=AMBER, text="Waiting for your R50…")
            self.live_sub.configure(bg=AMBER_BG, fg=AMBER,
                                    text="(make sure you finished Step 2)")
        elif state == "connected":
            self.chip.configure(bg=GREEN_BG)
            self._paint(self.chip_dot, self.chip_text, GREEN, GREEN_BG)
            self.chip_text.configure(text="Connected to your R50")
            self.live_box.configure(bg=GREEN_BG)
            self.live_dot.configure(bg=GREEN_BG, fg=GREEN)
            self.live_status.configure(bg=GREEN_BG, fg=GREEN,
                                       text="✅  Connected! Take a swing.")
            self.live_sub.configure(bg=GREEN_BG, fg=GREEN,
                                    text="Each shot will pop up below.")
        elif state == "shot":
            self.chip.configure(bg=GREEN_BG)
            self._paint(self.chip_dot, self.chip_text, GREEN, GREEN_BG)
            self.chip_text.configure(text=f"{self.shot_count} shot(s) captured")
        elif state == "error":
            self.chip.configure(bg=RED_BG)
            self._paint(self.chip_dot, self.chip_text, RED, RED_BG)
            self.chip_text.configure(text="Needs attention")
            if msg:
                self.err_text.configure(text=msg)
                self.err_banner.pack(fill="x", padx=24, pady=(0, 4),
                                     before=self.card)

    def _clear_error(self):
        self.err_banner.pack_forget()

    # --------------------------- networking engine --------------------------
    def _write_file(self, obj):
        if not self.logfile:
            return
        try:
            with self.file_lock:
                self.logfile.write(json.dumps(obj) + "\n")
                self.logfile.flush()
        except Exception:
            pass

    def _send(self, sock, obj):
        try:
            sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            self._write_file({"ts": datetime.now().isoformat(), "dir": "out", "msg": obj})
        except Exception as e:
            self.q.put(("log", f"[{now_str()}] send error: {e}"))

    def _on_message(self, obj, source, sock):
        self.msg_count += 1
        self._write_file({"ts": datetime.now().isoformat(), "source": source,
                          "dir": "in", "msg": obj})
        sdo = obj.get("ShotDataOptions") or {}
        is_hb = bool(sdo.get("IsHeartBeat"))
        ts = now_str()

        if is_hb:
            self.hb_count += 1
            self.q.put(("log", f"[{ts}] <heartbeat> from {source}"))
        else:
            self.shot_count += 1
            bd = obj.get("BallData") or {}
            cd = obj.get("ClubData") or {}
            has_club = bool(sdo.get("ContainsClubData")) or bool(cd)
            self.q.put(("shot_friendly", {
                "n": obj.get("ShotNumber") or self.shot_count,
                "ball": bd.get("Speed"), "launch": bd.get("VLA"),
                "spin": bd.get("TotalSpin"), "carry": bd.get("CarryDistance"),
                "has_club": has_club,
            }))
            self.q.put(("shot_row", (
                ts, obj.get("ShotNumber", ""), fmt(bd.get("Speed")), fmt(bd.get("VLA")),
                fmt(bd.get("HLA")), fmt(bd.get("TotalSpin")), fmt(bd.get("SpinAxis")),
                fmt(cd.get("Speed")), fmt(cd.get("Path")), fmt(cd.get("FaceToTarget")),
                fmt(bd.get("CarryDistance")), "YES" if has_club else "no",
            )))
            self.q.put(("log", f"[{ts}] *** SHOT #{obj.get('ShotNumber','?')} from {source} ***"))
            self.q.put(("log", "           " + json.dumps(obj)))

        self.q.put(("count", None))
        self._send(sock, {"Code": 200, "Message": "OK"})

    def _handle_conn(self, sock, source):
        self.q.put(("connected", source))
        self.q.put(("log", f"[{now_str()}] CONNECTED: {source}"))
        self._send(sock, {"Code": 201, "Message": "SUCCESS",
                          "Player": {"Handed": "RH", "Club": "DR"}})
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
                    self._on_message(obj, source, sock)
        finally:
            try:
                sock.close()
            except Exception:
                pass
            self.q.put(("log", f"[{now_str()}] DISCONNECTED: {source}"))
            self.q.put(("disconnected", source))

    def _server_loop(self, port):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", port))
            srv.listen(5)
            srv.settimeout(1.0)
            self.server_sock = srv
            self.q.put(("log", f"[{now_str()}] LISTENING on 0.0.0.0:{port}"))
            self.q.put(("engine_ready", None))
        except Exception as e:
            self.q.put(("bind_error", str(e)))
            return
        while self.running:
            try:
                conn, addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._handle_conn,
                             args=(conn, f"{addr[0]}:{addr[1]}"), daemon=True).start()
        try:
            srv.close()
        except Exception:
            pass

    def _probe_loop(self, target_ip, port):
        if not target_ip:
            return
        while self.running:
            try:
                sock = socket.create_connection((target_ip, port), timeout=3)
            except Exception:
                time.sleep(3)
                continue
            self._handle_conn(sock, f"PROBE->{target_ip}:{port}")
            if self.running:
                time.sleep(3)

    def _get_settings(self):
        # advanced window may override; otherwise defaults
        port = PORT_DEFAULT
        mode = "Both (auto)"
        probe = guess_gateway(get_primary_ip())
        if self.adv is not None:
            try:
                port = int(self.adv_port.get())
            except Exception:
                port = PORT_DEFAULT
            mode = self.adv_mode.get()
            probe = self.adv_probe.get().strip() or probe
        return port, mode, probe

    def start_engine(self):
        if self.running:
            return
        self._clear_error()
        port, mode, probe = self._get_settings()
        folder = app_dir()
        self.logpath = os.path.join(folder, "spike_log_" +
                                    datetime.now().strftime("%Y%m%d_%H%M%S") + ".jsonl")
        try:
            self.logfile = open(self.logpath, "a", encoding="utf-8")
        except Exception:
            self.logfile = None
        self.running = True
        self.connected = False
        self.msg_count = self.shot_count = self.hb_count = 0
        self._set_state("starting")
        if mode in ("Listen (recommended)", "Both (auto)"):
            threading.Thread(target=self._server_loop, args=(port,), daemon=True).start()
        if mode in ("Probe R50", "Both (auto)"):
            threading.Thread(target=self._probe_loop, args=(probe, port), daemon=True).start()

    def stop_engine(self):
        self.running = False
        try:
            if self.server_sock:
                self.server_sock.close()
        except Exception:
            pass
        self.server_sock = None
        if self.logfile:
            try:
                self.logfile.flush()
                self.logfile.close()
            except Exception:
                pass
            self.logfile = None

    def restart_engine(self):
        self.stop_engine()
        self._clear_error()
        self.root.after(400, self.start_engine)

    # --------------------------- friendly shot display ----------------------
    def _show_shot(self, d):
        self._set_state("shot")
        # also make sure step 3 live box is green
        self.live_box.configure(bg=GREEN_BG)
        self.live_dot.configure(bg=GREEN_BG, fg=GREEN)
        self.live_status.configure(bg=GREEN_BG, fg=GREEN, text="✅  Connected! Keep swinging.")
        self.live_sub.configure(bg=GREEN_BG, fg=GREEN, text="Your latest shot:")
        self.shot_big.configure(text=f"✅  Shot #{d['n']} captured!")
        parts = [f"Ball speed: {rint(d['ball'])} mph",
                 f"Launch: {rint(d['launch'])}°",
                 f"Spin: {rint(d['spin'])} rpm"]
        if d.get("carry") is not None:
            parts.append(f"Carry: {rint(d['carry'])} yds")
        self.shot_detail.configure(text="    ".join(parts))
        if d["has_club"]:
            self.shot_club.configure(text="Club data: included ✓", fg=GREEN)
        else:
            self.shot_club.configure(text="Club data: not included (ball only)", fg=AMBER)
        self.shot_total_lbl.configure(text=f"Shots captured so far: {self.shot_count}")

    # --------------------------- queue pump ---------------------------------
    def _drain_queue(self):
        try:
            while True:
                kind, payload = self.q.get_nowait()
                if kind == "connected":
                    if not self.connected:
                        self.connected = True
                        self._set_state("connected")
                        if self.current_step < 3:
                            self.show_step(3)
                elif kind == "disconnected":
                    self.connected = False
                    if self.running:
                        self._set_state("waiting")
                elif kind == "engine_ready":
                    if not self.connected:
                        self._set_state("waiting")
                elif kind == "bind_error":
                    self._set_state("error", self._bind_error_msg(payload))
                elif kind == "shot_friendly":
                    self._show_shot(payload)
                elif kind == "shot_row":
                    self.shots_buffer.append(payload)
                    if self.adv is not None:
                        self.adv_tree.insert("", "end", values=payload)
                        self.adv_tree.yview_moveto(1.0)
                elif kind == "log":
                    self.log_buffer.append(payload)
                    if len(self.log_buffer) > 4000:
                        self.log_buffer = self.log_buffer[-3000:]
                    if self.adv is not None:
                        self._adv_log(payload)
                elif kind == "count":
                    if self.adv is not None:
                        self.adv_count.set(
                            f"Messages: {self.msg_count}    Shots: {self.shot_count}"
                            f"    Heartbeats: {self.hb_count}")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_queue)

    def _bind_error_msg(self, raw):
        return ("This computer’s golf connection (port 921) is already in use — "
                "usually that means GSPro (or another golf app) is already open. "
                "Please fully close GSPro, then click “Try again”. "
                f"\n(Technical detail: {raw})")

    # --------------------------- network poll (step 2 hint) -----------------
    def _poll_network(self):
        ip = get_primary_ip()
        if ip != self.last_ip:
            self.last_ip = ip
            self.addr_var.set(ip)
            if ip != self.initial_ip:
                self.hint_var.set("✅  Looks like this computer joined a new Wi-Fi "
                                  "— that’s probably your R50. Move to Step 3.")
        self.root.after(2000, self._poll_network)

    # --------------------------- finish / files -----------------------------
    def finish_and_open(self):
        # Open the folder holding the shot log, cross-platform (Windows / macOS /
        # Linux) so the "all done" button works on the brother's Mac too.
        path = app_dir()
        try:
            if sys.platform == "darwin":            # macOS
                import subprocess
                subprocess.Popen(["open", path])
            elif os.name == "nt":                    # Windows
                os.startfile(path)                   # noqa: SLF / win-only
            else:                                     # Linux
                import subprocess
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

    # --------------------------- technical window ---------------------------
    def open_advanced(self):
        if self.adv is not None:
            try:
                self.adv.lift()
                return
            except Exception:
                self.adv = None
        win = tk.Toplevel(self.root)
        win.title("Technical details")
        win.geometry("980x620")
        self.adv = win

        top = ttk.Frame(win)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Point R50 at this IP:").grid(row=0, column=0, sticky="w")
        ttk.Label(top, textvariable=self.addr_var, font=F(11, True),
                  foreground=GREEN).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Button(top, text="Refresh IPs",
                   command=lambda: self.addr_var.set(get_primary_ip())).grid(row=0, column=2, padx=6)

        ttk.Label(top, text="Port:").grid(row=1, column=0, sticky="e", pady=4)
        self.adv_port = tk.StringVar(value=str(PORT_DEFAULT))
        ttk.Entry(top, textvariable=self.adv_port, width=8).grid(row=1, column=1, sticky="w")
        ttk.Label(top, text="Mode:").grid(row=1, column=2, sticky="e")
        self.adv_mode = tk.StringVar(value="Both (auto)")
        ttk.Combobox(top, textvariable=self.adv_mode, width=20, state="readonly",
                     values=["Both (auto)", "Listen (recommended)", "Probe R50"]
                     ).grid(row=1, column=3, sticky="w", padx=4)
        ttk.Label(top, text="Probe IP:").grid(row=1, column=4, sticky="e")
        self.adv_probe = tk.StringVar(value=guess_gateway(get_primary_ip()))
        ttk.Entry(top, textvariable=self.adv_probe, width=16).grid(row=1, column=5, sticky="w")
        ttk.Button(top, text="Apply & restart",
                   command=self.restart_engine).grid(row=1, column=6, padx=8)

        self.adv_count = tk.StringVar(
            value=f"Messages: {self.msg_count}    Shots: {self.shot_count}    Heartbeats: {self.hb_count}")
        ttk.Label(win, textvariable=self.adv_count).pack(anchor="w", padx=12)

        tf = ttk.LabelFrame(win, text="Shots")
        tf.pack(fill="x", padx=10, pady=6)
        cols = ("time", "shot", "ballspd", "vla", "hla", "spin", "axis",
                "clubspd", "path", "face", "carry", "club?")
        heads = ("Time", "Shot#", "BallSpd", "VLA", "HLA", "TotalSpin", "SpinAxis",
                 "ClubSpd", "ClubPath", "Face", "Carry", "Club?")
        self.adv_tree = ttk.Treeview(tf, columns=cols, show="headings", height=7)
        for c, h in zip(cols, heads):
            self.adv_tree.heading(c, text=h)
            self.adv_tree.column(c, width=78, anchor="center")
        self.adv_tree.column("time", width=100)
        self.adv_tree.pack(side="left", fill="x", expand=True)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.adv_tree.yview)
        sb.pack(side="right", fill="y")
        self.adv_tree.configure(yscrollcommand=sb.set)
        for row in self.shots_buffer:
            self.adv_tree.insert("", "end", values=row)

        lf = ttk.LabelFrame(win, text="Raw log")
        lf.pack(fill="both", expand=True, padx=10, pady=6)
        self.adv_logbox = tk.Text(lf, height=10, wrap="word", state="disabled",
                                 font=("Consolas", 9), background="#111", foreground="#ddd")
        self.adv_logbox.pack(side="left", fill="both", expand=True)
        lsb = ttk.Scrollbar(lf, orient="vertical", command=self.adv_logbox.yview)
        lsb.pack(side="right", fill="y")
        self.adv_logbox.configure(yscrollcommand=lsb.set)
        self.adv_logbox.configure(state="normal")
        self.adv_logbox.insert("end", "\n".join(self.log_buffer[-1000:]) + "\n")
        self.adv_logbox.configure(state="disabled")

        bf = ttk.Frame(win)
        bf.pack(fill="x", padx=10, pady=6)
        ttk.Button(bf, text="Open log folder", command=self.finish_and_open).pack(side="left")

        def on_close():
            self.adv = None
            win.destroy()
        win.protocol("WM_DELETE_WINDOW", on_close)

    def _adv_log(self, msg):
        self.adv_logbox.configure(state="normal")
        self.adv_logbox.insert("end", msg + "\n")
        self.adv_logbox.see("end")
        self.adv_logbox.configure(state="disabled")

    def show_help(self):
        top = tk.Toplevel(self.root)
        top.title("Help")
        top.geometry("720x560")
        txt = tk.Text(top, wrap="word", font=F(10))
        txt.pack(fill="both", expand=True, padx=8, pady=8)
        txt.insert("1.0", RUNBOOK_TEXT)
        txt.configure(state="disabled")

    def _on_close(self):
        self.stop_engine()
        self.root.destroy()


RUNBOOK_TEXT = """WHAT THIS DOES
It catches the shot data from your Garmin R50 so we can confirm everything
works. The app runs itself - you just follow the 3 steps on screen and swing.

THE 3 STEPS
1) On the R50: tap Connect, then GSPro. It shows a Wi-Fi name + password.
2) On this computer: click the Wi-Fi icon (bottom-right) and join that R50
   Wi-Fi, using the password from the R50 screen.
3) On the R50 it connects automatically. Then hit a shot. Each shot pops up.

IF IT SAYS "WAITING" AND NOTHING HAPPENS
- Make sure this computer is connected to the R50's Wi-Fi (Step 2), not the
  house Wi-Fi.
- Give the R50 10-20 seconds after Step 2 to find the app.
- If the R50 asks you to type an "address", use the address shown on Step 2/3
  and the port number 921.

IF IT SAYS "NEEDS ATTENTION / port in use"
- Another golf app (like GSPro) is already open. Fully close it, then click
  "Try again".

WHEN YOU'RE DONE
- Click "All done - get the file to send" (or Technical details > Open log
  folder). Send back the file named  spike_log_<date>.jsonl.
"""


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        r = tk.Tk()
        App(r)
        r.update()
        r.destroy()
        print("selftest ok")
        sys.exit(0)
    try:
        main()
    except Exception:
        import traceback
        tb = traceback.format_exc()
        try:
            with open(os.path.join(app_dir(), "spike_startup_error.txt"), "w",
                      encoding="utf-8") as fh:
                fh.write(tb)
        except Exception:
            pass
        try:
            from tkinter import messagebox
            messagebox.showerror("Spike Listener crashed at startup", tb)
        except Exception:
            pass
        raise
