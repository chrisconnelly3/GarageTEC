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
