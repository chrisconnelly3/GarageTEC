"""Extract a per-frame pose skeleton (and detect swing-phase times) from the
demo swing clip so the Live screen can draw a toggleable exoskeleton overlay
and the position stepper lines up with the real video.

The demo clip is a rotated two-view composite (down-the-line | face-on, side by
side once the .mov rotation flag is honored). MediaPipe Pose tracks one person
per image, so we run it on each half separately and merge the landmarks into a
single full-frame normalized coordinate space (x in [0,1] across BOTH views).

Output: <video>.pose.json next to the clip:
  {
    "fps": 32.8, "width": 2428, "height": 1284,
    "frames": [ { "poses": [ [[x,y,v], ...33], [[x,y,v], ...33] ] }, ... ]
  }
and prints detected phase times (seconds) for the seed to use.
"""
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import mediapipe as mp

# Landmarks we keep for the exoskeleton (BlazePose 33-point indices).
_VIS = 0.5


def _run_half(pose, bgr_half):
    """Return 33 [x,y,vis] (normalized to the half) or None if no person."""
    rgb = cv2.cvtColor(bgr_half, cv2.COLOR_BGR2RGB)
    res = pose.process(rgb)
    if not res.pose_landmarks:
        return None
    return [[round(lm.x, 4), round(lm.y, 4), round(lm.visibility, 3)]
            for lm in res.pose_landmarks.landmark]


def extract(video_path: Path):
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_ORIENTATION_AUTO, 1)  # honor the .mov rotation flag
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    mp_pose = mp.solutions.pose
    # PER-FRAME static detection (static_image_mode=True) at the most accurate
    # model (complexity=2). We deliberately do NOT use tracking mode /
    # smooth_landmarks: MediaPipe's velocity filter assumes smooth human motion
    # and visibly LAGS the ballistic downswing, leaving the arm skeleton bunched
    # up behind the real arms through transition/impact. Fresh per-frame
    # detection has a little more jitter but stays attached to the fast-moving
    # limbs, which matters far more for a golf swing. A single instance is fine
    # because static mode keeps no state between the two views.
    pose = mp_pose.Pose(static_image_mode=True, model_complexity=2,
                        min_detection_confidence=0.5)

    frames = []
    W = H = 0
    # Track the face-on (right view) lead-wrist Y per frame for phase detection.
    wrist_y = []  # (t, y) where y is normalized full-frame (0 top, 1 bottom)
    fi = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        H, W = frame.shape[:2]
        half = W // 2
        left = frame[:, :half]
        right = frame[:, half:]

        poses = []
        # LEFT view → x maps to [0, 0.5]
        pl = _run_half(pose, left)
        if pl:
            poses.append([[x * 0.5, y, v] for x, y, v in pl])
        # RIGHT view → x maps to [0.5, 1.0]
        pr = _run_half(pose, right)
        if pr:
            poses.append([[0.5 + x * 0.5, y, v] for x, y, v in pr])
            # right-wrist (15=left wrist,16=right wrist) — use the higher-vis one
            lw, rw = pr[15], pr[16]
            w = lw if lw[2] >= rw[2] else rw
            if w[2] > _VIS:
                wrist_y.append((fi / fps, w[1]))

        frames.append({"poses": poses})
        fi += 1
    cap.release()
    pose.close()
    return {"fps": round(fps, 4), "width": W, "height": H, "frames": frames}, wrist_y


def detect_phases(wrist_y, dur):
    """Heuristic phase times (s) from the face-on lead-wrist vertical track.
    y is normalized (0 = top of frame). Top of backswing = wrist highest = min y.
    Address = motion start; Impact = wrist returns near address height after top.
    Intermediate positions are placed proportionally between the anchors so the
    stepper is monotonic and visually matches the swing."""
    if len(wrist_y) < 5:
        # Fallback to evenly spread anchors across the clip.
        a, t, i = dur * 0.28, dur * 0.43, dur * 0.54
    else:
        ts = [t for t, _ in wrist_y]
        ys = [y for _, y in wrist_y]
        top_idx = int(np.argmin(ys))             # highest hands
        t_top = ts[top_idx]
        addr_y = float(np.median(ys[:max(3, top_idx // 3)]))  # resting height
        # Address: last sample before the top where the wrist is still ~resting.
        a = ts[0]
        for k in range(top_idx):
            if ys[k] <= addr_y - 0.04:           # started lifting
                a = ts[max(0, k - 1)]
                break
        t = t_top
        # Impact: after the top, the first time the wrist drops back to ~address.
        i = dur * 0.55
        for k in range(top_idx, len(ys)):
            if ys[k] >= addr_y - 0.02:
                i = ts[k]
                break
    # Build all eight positions, clamped and monotonic.
    def lerp(p, q, f):
        return p + (q - p) * f
    phases = {
        "address":     a,
        "takeaway":    lerp(a, t, 0.33),
        "lead-arm":    lerp(a, t, 0.66),
        "top":         t,
        "transition":  lerp(t, i, 0.20),
        "shaft par.":  lerp(t, i, 0.65),
        "impact":      i,
        "follow-thru": min(dur - 0.05, lerp(i, dur, 0.45)),
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
    phases = detect_phases(wrist_y, dur)
    data["phases"] = phases

    out = video.with_suffix(".pose.json")
    out.write_text(json.dumps(data), encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    n_with_pose = sum(1 for f in data["frames"] if f["poses"])
    print(f"wrote {out} ({size_kb:.0f} KB), {len(data['frames'])} frames, "
          f"{n_with_pose} with pose, {data['width']}x{data['height']}")
    print("detected phases (s):", json.dumps(phases))


if __name__ == "__main__":
    main()
