from dataclasses import dataclass, field
from typing import Optional, List


@dataclass
class Player:
    name: str
    height_in: float
    handedness: str  # "R" or "L"
    id: Optional[int] = None
    created_at: Optional[str] = None


@dataclass
class Session:
    player_id: int
    started_at: str
    ended_at: Optional[str] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Swing:
    session_id: int
    player_id: int
    created_at: str
    source_video_path: Optional[str] = None
    view_layout: Optional[str] = None
    fps: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    club: Optional[str] = None
    notes: Optional[str] = None
    shot_id: Optional[int] = None
    id: Optional[int] = None


@dataclass
class Shot:
    captured_at: str
    swing_id: Optional[int] = None
    player_id: Optional[int] = None
    session_id: Optional[int] = None
    device_id: Optional[str] = None
    shot_number: Optional[int] = None
    ball_speed: Optional[float] = None
    total_spin: Optional[float] = None
    spin_axis: Optional[float] = None
    hla: Optional[float] = None
    vla: Optional[float] = None
    carry: Optional[float] = None
    club_speed: Optional[float] = None
    attack_angle: Optional[float] = None
    club_path: Optional[float] = None
    face_to_target: Optional[float] = None
    raw_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Landmark:
    name: str
    x: float
    y: float
    z: float
    visibility: float


@dataclass
class PoseFrame:
    swing_id: int
    view: str
    frame_index: int
    time_s: float
    landmarks: List[Landmark] = field(default_factory=list)
    source: str = "mediapipe_pose"
    id: Optional[int] = None


@dataclass
class Moment:
    swing_id: int
    kind: str
    view: Optional[str] = None
    frame_index: Optional[int] = None
    time_s: Optional[float] = None
    id: Optional[int] = None


@dataclass
class Metric:
    swing_id: int
    name: str
    context: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    method: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Media:
    swing_id: int
    kind: str
    path: str
    meta_json: Optional[str] = None
    id: Optional[int] = None


@dataclass
class Coaching:
    swing_id: Optional[int]
    session_id: Optional[int]
    kind: str  # "swing" or "session"
    content_json: str
    model: Optional[str] = None
    created_at: Optional[str] = None
    id: Optional[int] = None
