# metrics/geometry3d.py
"""3D vector helpers for triangulated-pose metrics. World frame: up = +Y,
target_line = +X, depth = +Z. All inputs are numpy 3-vectors."""
import math
import numpy as np


def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def project_to_plane(v, axis):
    """Component of v orthogonal to `axis` (the plane with normal `axis`)."""
    axis = _unit(axis)
    return v - np.dot(v, axis) * axis


def turn_about_axis(seg_address, seg_current, up):
    """Signed angle (deg) the segment rotated about `up`, from its address
    orientation to current. Both projected onto the plane normal to `up`."""
    a = _unit(project_to_plane(np.asarray(seg_address, float), up))
    b = _unit(project_to_plane(np.asarray(seg_current, float), up))
    cross = np.cross(a, b)
    sin = np.dot(_unit(np.asarray(up, float)), cross)
    cos = np.dot(a, b)
    return math.degrees(math.atan2(sin, cos))


def tilt_from_horizontal(seg, up):
    """Magnitude (deg) the segment is tilted away from horizontal (the plane
    normal to `up`). 0 = level, 90 = aligned with `up`."""
    seg = np.asarray(seg, float)
    up = _unit(np.asarray(up, float))
    horiz = project_to_plane(seg, up)
    return math.degrees(math.atan2(abs(np.dot(seg, up)),
                                   np.linalg.norm(horiz)))
