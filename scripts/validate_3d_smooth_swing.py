# scripts/validate_3d_smooth_swing.py
"""Manual validation (NOT a unit test): run the 3D pipeline on smooth_swing.mov
with the approximate calibration and print turn/X-factor. smooth_swing.mov is a
direct-export synced side-by-side clip (rotated 90 deg portrait -> rotate to
landscape first). Pass if shoulder turn @ top is ~80-95 deg and X-factor > 0.

Usage: python scripts/validate_3d_smooth_swing.py path/to/smooth_swing.mov
"""
import sys

from store import db as dbmod, repo
from vision.pipeline import process_video
from vision.threed.calibration import AssumedGeometryCalibration
from metrics.compute import compute_metrics


def main(video_path):
    conn = dbmod.connect(":memory:"); dbmod.init_db(conn=conn)
    pid = repo.get_or_create_player(conn, "Pro", 70.0, "R").id
    sid = repo.create_session(conn, pid).id
    # NOTE: smooth_swing.mov is portrait-rotated; rotate to landscape before this
    # (e.g. ffmpeg -vf "transpose=1") so the side-by-side split is correct.
    cal = AssumedGeometryCalibration(image_width=1214, image_height=1080,
                                     height_in=70.0)
    results = process_video(conn, video_path, player_id=pid, session_id=sid,
                            single_swing=True, calibration=cal)
    for res in results:
        metrics = compute_metrics(conn, res.swing_id)
        wanted = {(m.name, m.context): m.value for m in metrics
                  if m.method and m.method.startswith("triangulated_3d")}
        print("swing", res.swing_id)
        for k in sorted(wanted):
            print(f"   {k[0]}@{k[1]} = {wanted[k]:.1f} deg")
        st = wanted.get(("shoulder_turn_deg", "top"))
        if st is not None:
            ok = 70.0 <= abs(st) <= 100.0
            print(f"   shoulder turn @ top plausible (70-100): {ok}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "smooth_swing.mov")
