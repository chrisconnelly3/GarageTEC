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

# ---- swing detection (motion energy) ----
MOTION_SMOOTH_WINDOW = 5       # moving-average window for the energy signal
# A frame is "in motion" if energy >= this fraction of the per-video peak energy.
SWING_ENERGY_THRESH_FRAC = 0.15
MIN_SWING_FRAMES = 12          # reject motion bursts shorter than this (fidgets)
MIN_STILL_FRAMES = 4           # stillness frames required to close a swing window
# A burst must reach at least this fraction of peak energy to count as a swing.
MIN_PEAK_FRAC = 0.40
SWING_PAD_FRAMES = 3           # pad each window outward by this many frames (clamped)

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
