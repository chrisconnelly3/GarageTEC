"""CLI for the metrics brain.

    python -m metrics.run --swing 42
    python -m metrics.run --all-missing

Both accept an explicit DB via --db PATH (defaults to the store's default path).
The run(conn, argv) function takes an open connection so tests use :memory:.
"""
import argparse
import sys
from typing import List

from store import db as dbmod
from store import repo
from metrics.compute import compute_metrics


def swings_missing_metrics(conn) -> List[int]:
    """Swing ids that have zero metric rows, in id order."""
    rows = conn.execute(
        "SELECT sw.id FROM swing sw "
        "LEFT JOIN metric m ON m.swing_id = sw.id "
        "WHERE m.id IS NULL GROUP BY sw.id ORDER BY sw.id").fetchall()
    return [r["id"] for r in rows]


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metrics.run",
                                description="Compute swing metrics.")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--swing", type=int, help="compute metrics for one swing id")
    g.add_argument("--all-missing", action="store_true",
                   help="compute metrics for every swing lacking metrics")
    p.add_argument("--db", default=None, help="path to the SQLite db (optional)")
    return p


def run(conn, argv: List[str]) -> int:
    """Run with an already-open connection (used by tests and main)."""
    args = _build_parser().parse_args(argv)
    if args.swing is not None:
        written = compute_metrics(conn, args.swing)
        print(f"swing {args.swing}: wrote {len(written)} metrics")
        return 0
    ids = swings_missing_metrics(conn)
    total = 0
    for swing_id in ids:
        written = compute_metrics(conn, swing_id)
        total += len(written)
        print(f"swing {swing_id}: wrote {len(written)} metrics")
    print(f"done: {len(ids)} swings, {total} metrics")
    return 0


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Peek for --db without consuming the required mode group.
    db_path = None
    if "--db" in argv:
        i = argv.index("--db")
        db_path = argv[i + 1]
    conn = dbmod.connect(db_path)
    try:
        return run(conn, argv)
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
