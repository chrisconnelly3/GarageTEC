"""MetricContext: everything a metric fn needs for one swing.

Holds smoothed pose timelines (per view), a (view, kind) -> frame_index map,
the pixels-per-inch ruler from the player's height + address shoulder width,
and the player. Built from the store by build_context().
"""
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from store import repo
from store.models import Landmark, Player, PoseFrame
from metrics import geometry as g

# Number of frames in the centered moving-average smoothing window (odd).
SMOOTH_WINDOW = 3


@dataclass
class MetricContext:
    swing_id: int
    player: Player
    ppi: float
    fps: Optional[float]
    # view -> {frame_index -> landmarks}
    _pose: Dict[str, Dict[int, List[Landmark]]]
    # (view, kind) -> frame_index
    _moment_frame: Dict[Tuple[str, str], int]

    def frame_index_for(self, view: str, kind: str) -> Optional[int]:
        return self._moment_frame.get((view, kind))

    def frames(self, view: str) -> Dict[int, List[Landmark]]:
        return self._pose.get(view, {})

    def pose_at_frame(self, view: str, frame_index: int) -> Optional[List[Landmark]]:
        return self._pose.get(view, {}).get(frame_index)

    def pose_at(self, view: str, kind: str) -> Optional[List[Landmark]]:
        idx = self.frame_index_for(view, kind)
        if idx is None:
            return None
        return self.pose_at_frame(view, idx)


def _smooth(frames: List[PoseFrame], window: int) -> Dict[int, List[Landmark]]:
    """Centered moving average of each landmark's x/y across nearby frames.
    Only landmarks present in ALL frames of the window are averaged; otherwise
    the raw landmark at the center frame is kept. Returns {frame_index: lms}.
    """
    half = window // 2
    by_index = {f.frame_index: f for f in frames}
    order = sorted(by_index)
    pos = {idx: i for i, idx in enumerate(order)}
    out: Dict[int, List[Landmark]] = {}
    for idx in order:
        i = pos[idx]
        # Only average frames whose frame_index is within `half` of the center
        # (true temporal neighbours), not merely adjacent in array position.
        neighbours = [by_index[order[j]]
                      for j in range(max(0, i - half), min(len(order), i + half + 1))
                      if abs(order[j] - idx) <= half]
        center = by_index[idx]
        smoothed: List[Landmark] = []
        for lm in center.landmarks:
            xs, ys = [], []
            for nf in neighbours:
                n_lm = g.pick(nf.landmarks, lm.name)
                if n_lm is not None:
                    xs.append(n_lm.x)
                    ys.append(n_lm.y)
            ax = sum(xs) / len(xs) if xs else lm.x
            ay = sum(ys) / len(ys) if ys else lm.y
            smoothed.append(Landmark(name=lm.name, x=ax, y=ay, z=lm.z,
                                     visibility=lm.visibility))
        out[idx] = smoothed
    return out


def build_context(conn, swing_id: int) -> MetricContext:
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise ValueError(f"swing {swing_id} not found")
    player = repo.get_player(conn, swing.player_id)
    if player is None:
        raise ValueError(f"player {swing.player_id} for swing {swing_id} not found")

    pose: Dict[str, Dict[int, List[Landmark]]] = {}
    for view in ("face_on", "down_line"):
        frames = repo.get_pose_frames(conn, swing_id, view)
        pose[view] = _smooth(frames, SMOOTH_WINDOW) if frames else {}

    moment_frame: Dict[Tuple[str, str], int] = {}
    for m in repo.get_moments(conn, swing_id):
        if m.view is not None and m.frame_index is not None:
            moment_frame[(m.view, m.kind)] = m.frame_index

    ppi = _ppi_from_address(pose.get("face_on", {}), moment_frame, player)

    return MetricContext(swing_id=swing_id, player=player, ppi=ppi,
                         fps=swing.fps, _pose=pose, _moment_frame=moment_frame)


def _ppi_from_address(face_on: Dict[int, List[Landmark]],
                      moment_frame: Dict[Tuple[str, str], int],
                      player: Player) -> float:
    idx = moment_frame.get(("face_on", "address"))
    if idx is None or idx not in face_on:
        return 0.0
    lms = face_on[idx]
    ls = g.pick(lms, "left_shoulder")
    rs = g.pick(lms, "right_shoulder")
    if ls is None or rs is None:
        return 0.0
    shoulder_px = abs(rs.x - ls.x)
    return g.ppi_from_height(shoulder_px, player.height_in)
