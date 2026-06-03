"""CLI: generate coaching for a swing or session.

    python -m coach.run --swing 12
    python -m coach.run --session 3 --backend local

Backend defaults to cloud (Anthropic); override with --backend or COACH_BACKEND.
Tests call _run() with an injected conn + backend, so no network is required.
"""
import argparse
import json
import sys

from store import db as dbmod
from coach import coach
from coach.backend import make_backend


def _build_parser():
    p = argparse.ArgumentParser(prog="coach.run",
                                description="Generate grounded swing coaching.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--swing", type=int, help="swing id to coach")
    g.add_argument("--session", type=int, help="session id to summarize")
    p.add_argument("--backend", default=None,
                   help="backend name (cloud|local|fake); default cloud")
    p.add_argument("--db", default=None, help="sqlite path (default: app data db)")
    return p


def _run(argv, conn=None, backend=None):
    args = _build_parser().parse_args(argv)
    own_conn = conn is None
    if conn is None:
        conn = dbmod.connect(args.db)
        dbmod.init_db(conn=conn)
    if backend is None:
        backend = make_backend(args.backend)
    try:
        if args.swing is not None:
            row = coach.coach_swing(conn, backend, args.swing)
        else:
            row = coach.coach_session(conn, backend, args.session)
        print(json.dumps(json.loads(row.content_json), indent=2))
        return 0
    finally:
        if own_conn:
            conn.close()


def main():
    sys.exit(_run(sys.argv[1:]))


if __name__ == "__main__":
    main()
