"""TrackMan PGA Tour Averages (per club) + ball-data 'vs ideal' comparison.

Source: TrackMan "PGA Tour Averages" (https://www.trackmangolf.com). PGA TOUR
(male professional) averages — aspirational benchmarks, not pass/fail.

ONLY the metrics the Garmin R50 actually passes over the GSPro Open Connect
protocol (TCP 921) are compared. Open Connect BallData = Speed, SpinAxis,
Total/Back/SideSpin, HLA, VLA, CarryDistance; ClubData = Speed, AngleOfAttack,
FaceToTarget, Path, ... So the chart's **Max Height** and **Land Angle** are
intentionally EXCLUDED — they are not in the protocol (the launch monitor sends
launch conditions; flight apex/descent are simulator outputs, not passed to us).
Smash factor is derived (ball_speed / club_speed).
"""

# club -> tour-average targets. Keys map to Shot fields (or derived):
#   club_speed (mph), attack_angle (deg), ball_speed (mph), smash (ratio),
#   launch = Shot.vla (deg), spin = Shot.total_spin (rpm), carry (yds)
TRACKMAN = {
    "Driver":  {"club_speed": 113, "attack_angle": -1.3, "ball_speed": 167, "smash": 1.48, "launch": 10.9, "spin": 2686, "carry": 275},
    "3 Wood":  {"club_speed": 107, "attack_angle": -2.9, "ball_speed": 158, "smash": 1.48, "launch": 9.2,  "spin": 3655, "carry": 243},
    "5 Wood":  {"club_speed": 103, "attack_angle": -3.3, "ball_speed": 152, "smash": 1.47, "launch": 9.4,  "spin": 4350, "carry": 230},
    "Hybrid":  {"club_speed": 100, "attack_angle": -3.5, "ball_speed": 146, "smash": 1.46, "launch": 10.2, "spin": 4437, "carry": 225},
    "3 Iron":  {"club_speed": 98,  "attack_angle": -3.1, "ball_speed": 142, "smash": 1.45, "launch": 10.4, "spin": 4630, "carry": 212},
    "4 Iron":  {"club_speed": 96,  "attack_angle": -3.4, "ball_speed": 137, "smash": 1.43, "launch": 11.0, "spin": 4836, "carry": 203},
    "5 Iron":  {"club_speed": 94,  "attack_angle": -3.7, "ball_speed": 132, "smash": 1.41, "launch": 12.1, "spin": 5361, "carry": 194},
    "6 Iron":  {"club_speed": 92,  "attack_angle": -4.1, "ball_speed": 127, "smash": 1.38, "launch": 14.1, "spin": 6231, "carry": 183},
    "7 Iron":  {"club_speed": 90,  "attack_angle": -4.3, "ball_speed": 120, "smash": 1.33, "launch": 16.3, "spin": 7097, "carry": 172},
    "8 Iron":  {"club_speed": 87,  "attack_angle": -4.5, "ball_speed": 115, "smash": 1.32, "launch": 18.1, "spin": 7998, "carry": 160},
    "9 Iron":  {"club_speed": 85,  "attack_angle": -4.7, "ball_speed": 109, "smash": 1.28, "launch": 20.4, "spin": 8647, "carry": 148},
    "PW":      {"club_speed": 83,  "attack_angle": -5.0, "ball_speed": 102, "smash": 1.23, "launch": 24.2, "spin": 9304, "carry": 136},
}

CLUBS = list(TRACKMAN)   # ordered Driver -> PW (selector order)

# (key, label, unit, "near" tolerance) — order shown in the panel.
_METRICS = [
    ("ball_speed",   "Ball speed",   "mph", 5),
    ("club_speed",   "Club speed",   "mph", 5),
    ("smash",        "Smash factor", "",    0.05),
    ("launch",       "Launch angle", "deg", 2),
    ("spin",         "Spin rate",    "rpm", 500),
    ("attack_angle", "Attack angle", "deg", 1.5),
    ("carry",        "Carry",        "yds", 10),
]


def _shot_value(shot, key):
    """Pull the comparable value from a shot dict; None if absent."""
    if key == "smash":
        cs, bs = shot.get("club_speed"), shot.get("ball_speed")
        return round(bs / cs, 2) if cs and bs and cs > 0 else None
    if key == "launch":
        return shot.get("vla")
    if key == "spin":
        return shot.get("total_spin")
    return shot.get(key)             # ball_speed, club_speed, attack_angle, carry


def benchmark_ball(shot, club, ref=None):
    """Compare a shot's R50 ball metrics to the TrackMan tour average for `club`.
    `shot` is a shot dict (or None); `club` is a TRACKMAN key (or None). Returns a
    list of {key, label, unit, value, target, delta, near} for the metrics the
    R50 actually reports (others skipped)."""
    ref = TRACKMAN if ref is None else ref
    row = ref.get(club) if club else None
    if shot is None or row is None:
        return []
    out = []
    for key, label, unit, tol in _METRICS:
        v = _shot_value(shot, key)
        if v is None:
            continue
        target = row[key]
        delta = round(v - target, 2)
        out.append({"key": key, "label": label, "unit": unit,
                    "value": v, "target": target, "delta": delta,
                    "near": abs(delta) <= tol})
    return out
