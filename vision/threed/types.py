from dataclasses import dataclass, field
from typing import List, Optional

from store.models import Landmark3D


@dataclass
class Pose3DTimeline:
    """Parallel lists over composite frames. frames[i] = list[Landmark3D] in
    metric world coords, or None if that frame could not be reconstructed."""
    times_s: List[float] = field(default_factory=list)
    frames: List[Optional[List[Landmark3D]]] = field(default_factory=list)

    def __len__(self):
        return len(self.frames)
