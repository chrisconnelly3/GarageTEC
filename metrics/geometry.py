"""Pure geometry for swing metrics. No store imports; operates on Landmark
objects (with pixel .x/.y) and (x, y) tuples. Image coordinates: y grows
DOWNWARD, x grows toward image-right.
"""
import math
from typing import List, Optional, Tuple

from store.models import Landmark

Point = Tuple[float, float]

# Anthropometric ratio: biacromial (shoulder) breadth ~= 0.24 * standing height.
SHOULDER_HEIGHT_RATIO = 0.24


def pick(landmarks: List[Landmark], name: str) -> Optional[Landmark]:
    """Return the landmark with this name, or None if absent."""
    for lm in landmarks:
        if lm.name == name:
            return lm
    return None


def midpoint(a: Landmark, b: Landmark) -> Point:
    return ((a.x + b.x) / 2.0, (a.y + b.y) / 2.0)


def line_angle_vs_horizontal(a: Landmark, b: Landmark) -> float:
    """Signed angle (deg) of the line a->b relative to the horizontal axis.
    Because image-y points down, we negate dy so that 'b higher than a'
    (smaller y) yields a positive angle. Range (-90, 90].
    """
    dx = b.x - a.x
    dy = b.y - a.y
    return math.degrees(math.atan2(-dy, dx))


def line_angle_vs_vertical(top: Landmark, bottom: Landmark) -> float:
    """Unsigned-magnitude lean (deg) of the segment top..bottom from a plumb
    vertical line. 0 = perfectly vertical. Uses horizontal run over vertical
    drop: atan2(|dx|, |dy|).
    """
    dx = top.x - bottom.x
    dy = top.y - bottom.y
    return math.degrees(math.atan2(abs(dx), abs(dy)))


def lateral_displacement(ref: Point, cur: Point) -> float:
    """Signed horizontal pixel displacement (cur.x - ref.x)."""
    return cur[0] - ref[0]


def forward_vertical_displacement(ref: Point, cur: Point) -> Tuple[float, float]:
    """Return (forward_px, vertical_px) = (cur.x - ref.x, cur.y - ref.y).
    Vertical is signed image-y delta (negative = moved up / stood taller).
    """
    return (cur[0] - ref[0], cur[1] - ref[1])


def ppi_from_height(shoulder_px: float, height_in: float) -> float:
    """Pixels-per-inch from the Slice-1 ruler:
    ppi = shoulder_px / (0.24 * height_in). Returns 0.0 if undefined.
    """
    real_shoulder_in = SHOULDER_HEIGHT_RATIO * height_in
    if real_shoulder_in <= 0.0:
        return 0.0
    return shoulder_px / real_shoulder_in


def foreshortening_to_rotation_deg(current_width_px: float,
                                   address_width_px: float) -> float:
    """Rough 2D rotation estimate from segment-width foreshortening.
    A line of true length W projects to W*cos(theta) when rotated theta about a
    vertical axis, so theta = arccos(current / address). Full width -> 0 deg,
    half width -> 60 deg. Ratio clamped to [0, 1]; returns 0 if address width
    is non-positive. COARSE: callers must tag confidence=low.
    """
    if address_width_px <= 0.0:
        return 0.0
    ratio = current_width_px / address_width_px
    ratio = max(0.0, min(1.0, ratio))
    return math.degrees(math.acos(ratio))
