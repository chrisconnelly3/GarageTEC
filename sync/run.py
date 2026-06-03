"""CLI: reconcile swing<->shot links for one session or all sessions.

    python -m sync.run --session 7
    python -m sync.run --all
    python -m sync.run --session 7 --threshold 0.8
"""

import argparse
import sys

from store import db as dbmod
from sync.service import SyncService, DEFAULT_THRESHOLD


def _build_parser():
    p = argparse.ArgumentParser(prog="sync.run",
                                description="Reconcile swing<->shot links.")
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument("--session", type=int, help="Reconcile one session id.")
    group.add_argument("--all", action="store_true",
                       help="Reconcile every session.")
    p.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                   help="Auto-link confidence threshold (default %(default)s).")
    return p


def main(argv=None, *, conn=None):
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        # argparse exits 2 on usage error; surface that as our return code.
        return int(e.code) if e.code is not None else 2

    owns_conn = conn is None
    conn = conn or dbmod.connect()
    try:
        svc = SyncService(conn, threshold=args.threshold)
        if args.all:
            result = svc.reconcile_all()
            print(f"reconcile_all: linked {result['linked_count']} pair(s)")
        else:
            result = svc.reconcile_session(session_id=args.session)
            print(f"session {args.session}: linked {len(result['linked'])} "
                  f"pair(s), {len(result['proposals'])} proposal(s) left")
        return 0
    finally:
        if owns_conn:
            conn.close()


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
