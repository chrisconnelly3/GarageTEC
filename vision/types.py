from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from store.models import Landmark, Moment


# A per-frame sample from a frame source: the frame index, its timestamp, and
# the per-view BGR crops. `view_crops` maps view name -> numpy BGR array.
@dataclass
class FrameSample:
    index: int
    time_s: float
    view_crops: Dict[str, object]  # {"down_line": ndarray, "face_on": ndarray}


# The cached pose timeline for ONE view: parallel lists over all frames.
# `frames[i]` is the list[Landmark] for frame i, or None if no pose was found.
@dataclass
class PoseTimeline:
    view: str
    times_s: List[float] = field(default_factory=list)
    frames: List[Optional[List[Landmark]]] = field(default_factory=list)

    def __len__(self):
        return len(self.frames)


# A detected swing: [start_index, end_index] inclusive, plus the peak-energy frame.
@dataclass
class SwingWindow:
    start_index: int
    end_index: int
    peak_index: int

    def length(self):
        return self.end_index - self.start_index + 1


# What the pipeline emits per detected swing (the streaming/live-ready unit).
@dataclass
class SwingResult:
    swing_id: int
    moments: List[Moment]
    frame_range: Tuple[int, int]
    view_layout: str
    media_paths: List[str] = field(default_factory=list)
