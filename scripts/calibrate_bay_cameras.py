# scripts/calibrate_bay_cameras.py
"""ONE-TIME CLI bay calibration (the in-app Connect card is the normal path).
Reads composite PNGs, detects the board, runs the engine, writes bay_calib.json.

Usage: python scripts/calibrate_bay_cameras.py <frames_dir> --cols 9 --rows 6 \
         --square-mm 25 --split 0.5 --out bay_calib.json
"""
import argparse, glob, json, os
import cv2
from vision.threed import checkerboard as cb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("frames_dir")
    ap.add_argument("--cols", type=int, default=9)
    ap.add_argument("--rows", type=int, default=6)
    ap.add_argument("--square-mm", type=float, default=25.0)
    ap.add_argument("--split", type=float, default=0.5)
    ap.add_argument("--out", default="bay_calib.json")
    a = ap.parse_args()

    objp = cb._object_points(a.cols, a.rows, a.square_mm / 1000.0)
    obj_list, fo_pts, dl_pts, size = [], [], [], None
    for path in sorted(glob.glob(os.path.join(a.frames_dir, "*.png"))):
        img = cv2.imread(path)
        det = cb.detect_board(img, a.cols, a.rows, a.split)
        if det.found_both:
            obj_list.append(objp.copy())
            fo_pts.append(det.fo_corners); dl_pts.append(det.dl_corners)
            half_w = int(img.shape[1] * (1 - a.split))
            size = (half_w, img.shape[0])
    if len(obj_list) < 8:
        raise SystemExit(f"only {len(obj_list)} usable pairs; need >= 8")
    res = cb.stereo_calibrate(obj_list, fo_pts, dl_pts, size, a.square_mm / 1000.0)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(res.calib, f, indent=2)
    print(f"wrote {a.out} from {res.n_poses} pairs, reproj err {res.reprojection_error:.3f}px")


if __name__ == "__main__":
    main()
