"""All tunable thresholds for the vision pipeline live here, in ONE place.

These are 2D heuristics tuned against `golf swing.MOV`. Expect to adjust them
after eyeballing the annotated clip. Keep magic numbers out of other modules.
"""

# ---- frame source ----
DEFAULT_SPLIT = 0.5            # fraction of width where left|right views divide
VIEW_DOWN_LINE = "down_line"   # left half
VIEW_FACE_ON = "face_on"       # right half
VIEW_LAYOUT = "side_by_side_LR"

# ---- pose ----
POSE_MODEL_COMPLEXITY = 1
POSE_MIN_DET_CONF = 0.5
POSE_MIN_TRK_CONF = 0.5
LANDMARK_SMOOTH_WINDOW = 5     # moving-average window (frames) for landmark series

# ---- swing detection (hand-position trajectory) ----
# A swing is ONE excursion-and-return of the hands away from the address rest
# region, NOT a burst of motion. A boundary is declared only when the hands
# RETURN to the address region and STAY there for a sustained minimum duration,
# so a mid-swing pause (top-of-backswing dwell or a lag-artifact freeze) can
# never split one swing. Defaults are tuned for SMOOTH ~30 fps video.

# Centered moving-average window (frames) applied to the hand-height trajectory.
# Wide enough to absorb jitter AND brief freezes without erasing the swing arc.
TRAJ_SMOOTH_WINDOW = 7
# The address rest region is |h - addr_level| <= ADDRESS_REGION_RADIUS_FRAC * span,
# where `span` is the full vertical travel of the smoothed signal. Hands inside
# this band count as "at address".
ADDRESS_REGION_RADIUS_FRAC = 0.18
# Frames of sustained low movement required at the START to lock the address
# level (the calm setup). Short relative to a swing.
ADDRESS_REST_FRAMES = 8
# THE CORE FIX: hands must sit inside the address region continuously for at
# least this many frames before a swing boundary is declared. ~0.8 s @ 30 fps.
# A momentary dwell mid-swing keeps the hands AWAY from address, so it never
# reaches this threshold and never triggers a boundary.
MIN_RETURN_FRAMES = 24
# An excursion must reach at least this fraction of the signal's full vertical
# span to count as a swing (rejects fidgets / waggles below it).
MIN_SWING_AMPLITUDE_FRAC = 0.35
# Reject excursions shorter than this many frames. A real golf swing window
# (address-departure -> apex -> follow-through -> sustained return) always spans
# ~1 s; the shortest real window observed on field clips was ~46 frames. A floor
# of 26 (~0.85 s @ 30 fps) sits safely below that yet firmly rejects sub-second
# blips (e.g. a spurious ~17-frame "swing" seen on a real multi-swing clip).
MIN_SWING_FRAMES = 26
# Pad each window outward by this many frames (clamped to the signal bounds).
SWING_PAD_FRAMES = 3

# ---- segmentation (8 phases) ----
PHASE_ORDER = (
    "address",
    "takeaway",
    "lead_arm_parallel",
    "top",
    "transition",
    "shaft_parallel_down",
    "impact",
    "early_follow_through",
)
# A phase is confidence-flagged low when its locator cannot find a clear feature.
CONF_HIGH = "high"
CONF_LOW = "low"
# shaft_parallel_down has no club to measure -> ALWAYS low confidence.
ALWAYS_LOW_CONF_PHASES = ("shaft_parallel_down",)
# Takeaway: first frame where hand speed exceeds this fraction of window peak speed.
TAKEAWAY_SPEED_FRAC = 0.10
# Lead-arm-parallel / shaft-parallel: |angle to horizontal| within this many deg.
HORIZONTAL_TOL_DEG = 12.0
# Early follow-through: this many frames after impact (clamped to window end).
FOLLOW_THROUGH_FRAMES = 6
# Impact: hands return within this fraction of the address->top hand-height span.
IMPACT_HEIGHT_TOL_FRAC = 0.20

# ---- render ----
RENDER_FOURCC = "mp4v"
SKELETON_THICKNESS = 2
LABEL_FONT_SCALE = 0.7

# 3D reconstruction (two-camera triangulation). Off unless a Calibration is
# passed to process_video; this documents the default focal/distance the
# AssumedGeometry provider uses when no checkerboard calibration exists.
THREED_DEFAULT_CAMERA_DISTANCE_M = 4.0
