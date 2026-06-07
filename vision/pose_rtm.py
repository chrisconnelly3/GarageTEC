"""RTMPose backend (via rtmlib + ONNX Runtime) — a drop-in for the BlazePose
PoseEstimator that tracks the arms/limbs far better under golf occlusion.

Design notes:
- TOP-DOWN, detect-once: the bay camera is fixed and the golfer stationary, so
  we run the YOLOX person detector ONCE per view to lock a generous crop box,
  then run only the fast pose model every frame. (Re-running the detector each
  frame is what made CPU throughput collapse to <1 fps.)
- Output is COCO-17, mapped to the SAME landmark names the metrics use
  (left/right shoulder, hip, wrist, nose, ...), so it feeds both the metric
  pipeline and the skeleton overlay from one detection pass.
- Models are fetched from a prioritized source list (official -> author ->
  mirror) into models/ and their SHA-256 is logged so a mirror file can be
  verified against the official hash before production use.
"""
import hashlib
import os
import urllib.request
from pathlib import Path
from typing import List, Optional

import cv2
import numpy as np

from store.models import Landmark

_MODELS_DIR = Path(__file__).resolve().parents[1] / "models"

# COCO-17 landmark index -> name (matches the names metrics/3D code references).
COCO17_NAMES = [
    "nose", "left_eye", "right_eye", "left_ear", "right_ear",
    "left_shoulder", "right_shoulder", "left_elbow", "right_elbow",
    "left_wrist", "right_wrist", "left_hip", "right_hip",
    "left_knee", "right_knee", "left_ankle", "right_ankle",
]

# Prioritized download sources per file (try in order). Official openmmlab is
# first (canonical, checksum it for prod); HuggingFace mirrors are the reachable
# fallback. `sha256` is the EXPECTED official hash when known (None -> just log).
_SOURCES = {
    "rtmpose-m.onnx": {
        "sha256": None,
        "urls": [
            # 1) official author repo (HuggingFace, Apache-2.0)
            "https://huggingface.co/Tau-J/RTMPose/resolve/main/onnx/rtmpose-m.onnx",
            # 3) community mirror (verify checksum before prod)
            "https://huggingface.co/bukuroo/RTMPose-ONNX/resolve/main/rtmpose-m.onnx",
        ],
    },
    "yolox_s.onnx": {
        "sha256": None,
        "urls": [
            "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_s.onnx",
        ],
    },
}


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_model(filename: str) -> str:
    """Return a local path to `filename`, downloading from the first reachable
    source if absent. Logs the SHA-256 (and verifies it when a hash is known)."""
    _MODELS_DIR.mkdir(parents=True, exist_ok=True)
    dst = _MODELS_DIR / filename
    spec = _SOURCES.get(filename, {})
    if not dst.exists():
        last_err = None
        for url in spec.get("urls", []):
            try:
                print(f"[pose_rtm] downloading {filename} <- {url}")
                req = urllib.request.Request(url, headers={"User-Agent": "garagetec"})
                with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as out:
                    out.write(r.read())
                if dst.stat().st_size > 1_000_000:
                    break
                dst.unlink(missing_ok=True)  # too small -> error page
            except Exception as e:  # noqa: BLE001 - try next source
                last_err = e
                dst.unlink(missing_ok=True)
        if not dst.exists():
            raise RuntimeError(f"could not fetch {filename}: {last_err}")
    digest = _sha256(dst)
    expected = spec.get("sha256")
    if expected and digest != expected:
        raise RuntimeError(f"{filename} sha256 mismatch: {digest} != {expected}")
    print(f"[pose_rtm] {filename} sha256={digest}"
          + ("" if expected else "  (UNVERIFIED — checksum vs official for prod)"))
    return str(dst)


def _providers_device() -> str:
    try:
        import onnxruntime as ort
        provs = ort.get_available_providers()
        if "CUDAExecutionProvider" in provs:
            return "cuda"
    except Exception:  # noqa: BLE001
        pass
    return "cpu"


class RTMPoseEstimator:
    """API-compatible with vision.pose.PoseEstimator (estimate/close)."""

    _shared = None  # (det, pose, device) shared across views to load ONNX once

    def __init__(self, view: str):
        self.view = view
        self._bbox = None  # locked person box (x1,y1,x2,y2) in view-pixel coords
        self._miss = 0
        self._init_models()

    @classmethod
    def _init_models(cls):
        if cls._shared is not None:
            return
        from rtmlib import YOLOX, RTMPose
        device = _providers_device()
        det = YOLOX(ensure_model("yolox_s.onnx"), model_input_size=(640, 640),
                    backend="onnxruntime", device=device)
        pose = RTMPose(ensure_model("rtmpose-m.onnx"), model_input_size=(192, 256),
                       backend="onnxruntime", device=device)
        cls._shared = (det, pose, device)
        print(f"[pose_rtm] RTMPose backend ready (device={device})")

    def _detect_box(self, bgr) -> Optional[list]:
        det = self._shared[0]
        boxes = det(bgr)
        if boxes is None or len(boxes) == 0:
            return None
        # Largest-area box (the golfer fills the most of the view).
        areas = [(b[2] - b[0]) * (b[3] - b[1]) for b in boxes]
        b = boxes[int(np.argmax(areas))]
        h, w = bgr.shape[:2]
        # Pad generously: arms swing high/wide, club extends up.
        pw = (b[2] - b[0]) * 0.25
        ph = (b[3] - b[1]) * 0.22
        return [max(0, b[0] - pw), max(0, b[1] - ph * 1.4),
                min(w, b[2] + pw), min(h, b[3] + ph)]

    def estimate(self, bgr) -> Optional[List[Landmark]]:
        det, pose, _ = self._shared
        # Detect-once: lock the crop box on the first confident detection; reuse.
        if self._bbox is None:
            self._bbox = self._detect_box(bgr)
        bbox = self._bbox if self._bbox is not None else [
            0, 0, bgr.shape[1], bgr.shape[0]]
        kpts, scores = pose(bgr, bboxes=[bbox])
        if kpts is None or len(kpts) == 0:
            return None
        k = kpts[0]
        s = scores[0]
        out: List[Landmark] = []
        for i, name in enumerate(COCO17_NAMES):
            out.append(Landmark(name=name, x=float(k[i][0]), y=float(k[i][1]),
                                z=0.0, visibility=float(s[i])))
        return out

    def close(self) -> None:
        pass  # shared ONNX sessions persist for the process
