"""GarageTEC desktop launcher.

Boots the FastAPI server (which also serves the prebuilt frontend) on a free
local port, then presents it in a native chromeless window (pywebview / Windows
WebView2) so it feels like a standalone app rather than a browser tab. While the
server warms up, the window shows an animated branded splash and swaps to the
app once it's ready.

Flags:
  --no-window   run the server only (no GUI) and open the default browser
  --no-browser  with --no-window, don't open a browser either (headless)
"""
import os
import socket
import sys
import threading
import time
import urllib.request
from pathlib import Path

HOST = "127.0.0.1"
PREFERRED_PORT = 8000


def _resource(*parts: str) -> str:
    """Absolute path to a bundled resource, working both frozen (PyInstaller
    sets sys._MEIPASS) and from source."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def _ensure_data_dir() -> str:
    """Resolve a writable per-user data dir and export it so store.db and
    deps.media_root both land there. The packaged source tree is read-only, so
    default to %LOCALAPPDATA%\\GarageTEC (or ~/.garagetec)."""
    base = os.environ.get("GARAGETEC_DATA_DIR")
    if not base:
        local = os.environ.get("LOCALAPPDATA")
        base = str(Path(local) / "GarageTEC" if local else Path.home() / ".garagetec")
    os.environ["GARAGETEC_DATA_DIR"] = base
    Path(base).mkdir(parents=True, exist_ok=True)
    return base


def _load_env_file(data_dir: str) -> None:
    """Load KEY=VALUE pairs from a .env the USER can actually reach.

    web.backend.app also reads a .env, but it resolves it relative to the source
    tree — which inside a frozen exe points into the read-only PyInstaller
    bundle, so a packaged user has nowhere to put one. Look in the two places a
    real user would: their data folder (survives reinstalls) and next to the exe
    (portable). Existing environment variables always win, and we set the vars
    before importing the app so its own loader is a no-op.
    """
    candidates = [Path(data_dir) / ".env"]
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).parent / ".env")
    else:
        candidates.append(Path(__file__).resolve().parent / ".env")

    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not os.environ.get(key):
                os.environ[key] = value.strip()
        print(f"  loaded settings from {path}")


def _pick_port(preferred: int = PREFERRED_PORT) -> int:
    """Use the preferred port when free; otherwise grab any free ephemeral port.
    Prevents the old failure mode where a busy port left the app silently
    pointing at whatever else was already serving there."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind((HOST, preferred))
            return preferred
        except OSError:
            pass
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, 0))
        return s.getsockname()[1]


def _start_server(port: int):
    """Run uvicorn in a daemon thread. Returns the server (already starting)."""
    import uvicorn
    from web.backend.app import app

    config = uvicorn.Config(app, host=HOST, port=port, log_level="warning")
    server = uvicorn.Server(config)
    # Signal handlers can only be installed on the main thread; we run off-thread.
    server.install_signal_handlers = lambda: None
    threading.Thread(target=server.run, daemon=True).start()
    return server


def _wait_for_server(url: str, timeout: float = 40.0) -> bool:
    """Poll the health endpoint until the server answers (or we give up)."""
    health = url.rstrip("/") + "/api/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=1) as r:
                if r.status == 200:
                    return True
        except Exception:
            time.sleep(0.25)
    return False


def main() -> None:
    data_dir = _ensure_data_dir()
    # Must run BEFORE web.backend.app is imported: its own loader only fills
    # variables that are still unset, so whatever we set here wins.
    _load_env_file(data_dir)

    # Create the schema on first run (idempotent).
    from store import db as dbmod
    dbmod.init_db()

    port = _pick_port()
    app_url = f"http://{HOST}:{port}/"

    headless = "--no-window" in sys.argv
    webview = None
    if not headless:
        try:
            import webview  # pywebview
        except Exception:
            webview = None

    _start_server(port)

    if webview is not None:
        # Native window: show the animated splash, then load the app once ready.
        splash = Path(_resource("assets", "loading.html")).as_uri()
        window = webview.create_window(
            "GarageTEC",
            url=splash,
            width=1440,
            height=900,
            min_size=(1024, 700),
            background_color="#0A0D0B",
            text_select=False,
        )

        def _boot():
            if _wait_for_server(app_url):
                window.load_url(app_url)
            else:
                window.load_html(
                    "<body style='background:#0A0D0B;color:#E7EEE9;font-family:"
                    "system-ui;display:grid;place-items:center;height:100vh;margin:0'>"
                    "<div>GarageTEC could not start. Please relaunch.</div></body>"
                )

        webview.start(_boot, icon=_resource("assets", "garagetec.ico"))
        return

    # Fallback: no GUI backend (or --no-window). Serve in the foreground.
    print(f"GarageTEC running at {app_url}  (data: {data_dir})")
    if not headless or "--no-browser" not in sys.argv:
        if "--no-browser" not in sys.argv:
            import webbrowser
            threading.Timer(1.5, lambda: webbrowser.open(app_url)).start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def _report_fatal(exc_text: str) -> None:
    """A windowed (no-console) build has nowhere to print a crash, so persist it
    and show a native message box."""
    try:
        log = Path(os.environ.get("GARAGETEC_DATA_DIR", ".")) / "launch-error.log"
        log.write_text(exc_text, encoding="utf-8")
    except Exception:
        pass
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(
            0, exc_text[-1500:], "GarageTEC failed to start", 0x10)
    except Exception:
        pass


if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback
        _report_fatal(traceback.format_exc())
        raise
