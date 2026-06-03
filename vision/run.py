"""CLI: process a recorded video into stored per-swing body data.

Usage:
  python -m vision.run --video "golf swing.MOV" --player Chris
  python -m vision.run --video range.mov --player Chris --render
  python -m vision.run --video clip.mov --player Chris --single-swing --session 4
"""
import argparse
import sys

from vision import constants as C
from vision.pipeline import process_video
from store import db as dbmod
from store import repo


def build_arg_parser():
    p = argparse.ArgumentParser(
        prog="vision.run",
        description="Video -> stored per-swing body data (pose + 8 phases).")
    p.add_argument("--video", required=True, help="path to the input video")
    p.add_argument("--player", required=True, help="player name (get-or-create)")
    p.add_argument("--height", type=float, default=72.0,
                   help="player height in inches (used when creating the player)")
    p.add_argument("--handedness", default="R", choices=["R", "L"])
    p.add_argument("--session", type=int, default=None,
                   help="existing session id; default reuses/creates an open one")
    p.add_argument("--split", type=float, default=C.DEFAULT_SPLIT,
                   help="fraction of width dividing left|right views")
    p.add_argument("--single-swing", dest="single_swing", action="store_true",
                   help="force exactly one swing (strongest window)")
    p.add_argument("--render", action="store_true",
                   help="also write an annotated clip per swing")
    p.add_argument("--out", default="swings", help="output dir for clips")
    p.add_argument("--db", default=None, help="sqlite path (default app DB)")
    return p


def resolve_player_and_session(conn, *, player, height_in, handedness,
                               session_id):
    pid = repo.get_or_create_player(conn, player, height_in, handedness).id
    if session_id is not None:
        return pid, session_id
    open_sess = repo.get_open_session(conn, pid)
    if open_sess is not None:
        return pid, open_sess.id
    return pid, repo.create_session(conn, pid).id


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    conn = dbmod.connect(args.db)
    dbmod.init_db(conn=conn)
    pid, sid = resolve_player_and_session(
        conn, player=args.player, height_in=args.height,
        handedness=args.handedness, session_id=args.session)

    def on_swing(result):
        print(f"[vision] stored swing id={result.swing_id} "
              f"frames={result.frame_range} moments={len(result.moments)}")

    results = process_video(
        conn, args.video, player_id=pid, session_id=sid, split=args.split,
        single_swing=args.single_swing, render=args.render, out_dir=args.out,
        on_swing=on_swing)
    print(f"[vision] done: {len(results)} swing(s) stored for player_id={pid}, "
          f"session_id={sid}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
