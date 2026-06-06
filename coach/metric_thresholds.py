"""Single source of truth for stoplight thresholds. Two boundaries per metric
create three zones: green <= first, yellow <= second, red > second. Distance is
measured from the tour target, applied per direction mode:
  match  -> |value - target| (either side is bad)
  range  -> |value - target| (target is a band midpoint; same math as match)
  higher -> max(0, target - value)  (above target is always green)
  lower  -> max(0, value - target)  (below target is always green)
All numbers are first-pass and intentionally easy to tune here.
"""

# metric_key -> (direction, green_boundary, yellow_boundary)
THRESHOLDS = {
    # --- body ---
    "shoulder_tilt_deg":     ("match",  3,    6),
    "hip_tilt_deg":          ("match",  3,    6),
    "spine_angle_deg":       ("match",  3,    6),
    "shoulder_turn_deg":     ("match",  5,    12),
    "hip_turn_deg":          ("match",  5,    10),
    "x_factor_deg":          ("match",  5,    10),
    "x_factor_stretch_deg":  ("match",  2,    4),
    # DIRECTIONAL SWAY — sign convention + handedness MUST be verified in the
    # real bay (see docs/bay-verification-checklist.md). A good real swing must
    # read GREEN for both RH and LH players.
    #
    # head_sway_in / hip_sway_in are SIGNED inches: metrics/defs/sway.py reports
    # "positive = toward target" and derives the sign from the player's own
    # net hip motion address->impact, so it self-normalizes for handedness.
    # We use "match" against a correctly-SIGNED target, which makes the zone
    # DIRECTIONAL: |value - target| is small only when the player moved the
    # GOOD way by ~the tour amount. Moving the WRONG way (opposite sign) lands
    # |value - target| ~= 2x the magnitude -> red, as intended.
    #   head @ top: good load is TRAIL-side -> NEGATIVE target (-4.5).
    #   hip @ top/impact: pros shift TOWARD target -> POSITIVE targets (3.9/1.6).
    "hip_sway_in":           ("match",  0.8,  1.8),
    "head_sway_in":          ("match",  1.5,  3),
    "early_extension_in":    ("lower",  1,    2),
    # --- ball (keys match ball_reference benchmark keys) ---
    "ball_speed":            ("higher", 2.5,  5),
    "club_speed":            ("higher", 2.5,  5),
    "smash":                 ("higher", 0.03, 0.05),
    "carry":                 ("higher", 5,    10),
    "launch":                ("match",  1,    2),
    "spin":                  ("match",  250,  500),
    "attack_angle":          ("match",  0.75, 1.5),
}


def direction_for(metric):
    cfg = THRESHOLDS.get(metric)
    return cfg[0] if cfg else None


def zone_for(metric, value, target):
    """Return 'green' | 'yellow' | 'red', or None when the metric is unknown or
    no target is available."""
    cfg = THRESHOLDS.get(metric)
    if cfg is None or value is None or target is None:
        return None
    direction, green, yellow = cfg
    d = value - target
    if direction == "higher":
        m = max(0.0, -d)
    elif direction == "lower":
        m = max(0.0, d)
    else:  # match, range
        m = abs(d)
    if m <= green:
        return "green"
    if m <= yellow:
        return "yellow"
    return "red"
