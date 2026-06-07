"""Extract a per-frame pose skeleton (and detect swing-phase times) from the
demo swing clip so the Live screen can draw a toggleable exoskeleton overlay
and the position stepper lines up with the real video.

Uses the SHARED RTMPose backend (vision.pose_rtm) — the same detector that feeds
the body-metric pipeline — so the overlay and the metrics come from one model.
RTMPose tracks the arms far better than BlazePose under golf occlusion.

The demo clip is a rotated two-view composite (down-the-line | face-on, side by
side once the .mov rotation flag is honored). We run the estimator on each half
(one per view, detect-once) and merge into a single full-frame normalized
coordinate space (x in [0,1] across BOTH views).

Output: <video>.pose.json next to the clip:
  {
    "fps": 32.8, "width": 2428, "height": 1284, "layout": "coco17",
    "frames": [ { "poses": [ [[x,y,v], ...17], [[x,y,v], ...17] ] }, ... ]
  }
and prints detected phase times (seconds).
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np

# Ensure repo root on path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from vision.pose_rtm import RTMPoseEstimator, COCO17_NAMES  # noqa: E402

_VIS = 0.5
_LWRIST = COCO17_NAMES.index("left_wrist")
_RWRIST = COCO17_NAMES.index("right_wrist")


def _lm_to_list(lms, x0, W, H):
    """Landmark list (view-pixel coords) -> [[x,y,v]*17] in full-frame norms."""
    return [[(x0 + l.x) / W, l.y / H, round(l.visibility, 3)] for l in lms]


def extract(video_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)  # honor the .mov rotation flag
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # One estimator per view (each locks its own detect-once crop box).
    left_est = RTMPoseEstimator(view="down_line")
    right_est = RTMPoseEstimator(view="face_on")

    frames = []
    W = H = 0
    wrist_y = []  # (t, y_norm) of the face-on lead wrist, for phase detection
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        H, W = frame.shape[:2]
        half = W // 2
        poses = []
        pl = left_est.estimate(frame[:, :half])
        if pl:
            poses.append([[round(x, 4), round(y, 4), v]
                          for x, y, v in _lm_to_list(pl, 0, W, H)])
        pr = right_est.estimate(frame[:, half:])
        if pr:
            poses.append([[round(x, 4), round(y, 4), v]
                          for x, y, v in _lm_to_list(pr, half, W, H)])
            lw, rw = pr[_LWRIST], pr[_RWRIST]
            w = lw if lw.visibility >= rw.visibility else rw
            if w.visibility > _VIS:
                wrist_y.append((fi / fps, w.y / H))
        frames.append({"poses": poses})
        fi += 1
    cap.release()
    left_est.close()
    right_est.close()
    return {"fps": round(fps, 4), "width": W, "height": H,
            "layout": "coco17", "frames": frames}, wrist_y


def detect_phases(wrist_y, dur):
    """Heuristic phase times (s) from the face-on lead-wrist vertical track.
    Demo-only and approximate; real captures get detected moments from the
    capture pipeline. (See bay-verification checklist.)"""
    if len(wrist_y) < 5:
        a, t, i = dur * 0.28, dur * 0.43, dur * 0.54
    else:
        ts = [t for t, _ in wrist_y]
        ys = [y for _, y in wrist_y]
        top_idx = int(np.argmin(ys[:max(5, int(len(ys) * 0.78))]))
        t_top = ts[top_idx]
        addr_y = float(np.median(ys[:max(3, top_idx // 3)]))
        a = ts[0]
        for k in range(top_idx):
            if ys[k] <= addr_y - 0.04:
                a = ts[max(0, k - 1)]
                break
        t = t_top
        i = dur * 0.55
        for k in range(top_idx, len(ys)):
            if ys[k] >= addr_y - 0.02:
                i = ts[k]
                break

    def lerp(p, q, f):
        return p + (q - p) * f
    phases = {
        "address": a, "takeaway": lerp(a, t, 0.33), "lead-arm": lerp(a, t, 0.66),
        "top": t, "transition": lerp(t, i, 0.20), "shaft par.": lerp(t, i, 0.65),
        "impact": i, "follow-thru": min(dur - 0.05, lerp(i, dur, 0.45)),
    }
    return {k: round(float(v), 3) for k, v in phases.items()}


def main():
    video = Path(sys.argv[1] if len(sys.argv) > 1
                 else "data/media/swings/smooth_swing.mov")
    if not video.exists():
        print(f"ERROR: {video} not found")
        sys.exit(1)
    data, wrist_y = extract(video)
    dur = len(data["frames"]) / data["fps"]
    data["phases"] = detect_phases(wrist_y, dur)
    out = video.with_suffix(".pose.json")
    out.write_text(json.dumps(data), encoding="utf-8")
    n_pose = sum(1 for f in data["frames"] if f["poses"])
    print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB), "
          f"{len(data['frames'])} frames, {n_pose} with pose, "
          f"{data['width']}x{data['height']}, layout=coco17")
    print("detected phases (s):", json.dumps(data["phases"]))


if __name__ == "__main__":
    main()
