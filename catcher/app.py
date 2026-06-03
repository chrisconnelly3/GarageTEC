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
