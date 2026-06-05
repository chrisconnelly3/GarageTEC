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
    "hip_sway_in":           ("lower",  0.5,  1.5),
    "head_sway_in":          ("range",  1.5,  3),
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
