"""System/user prompt templates, the strict JSON output schema, and validate().

validate() is the anti-generic gate: every finding must cite a metric that
actually appears in the grounding context, with a matching value, and must
compare to baseline and/or ideal. Malformed output is rejected (never stored).
"""
import json

SYSTEM = (
    "You are a PGA-Tour-caliber teaching professional reading a launch monitor "
    "and 3D body-capture report for one of your players. Your voice is that of a "
    "top instructor on the lesson tee: authoritative, precise, and genuinely "
    "invested in this player's improvement. You speak in plain, confident "
    "language a serious golfer respects -- you connect the numbers to cause and "
    "effect in the swing and to what the ball actually did, you lead with what "
    "is working before what needs work, and you are honest about flaws without "
    "being discouraging. You never pad with generic platitudes; every sentence "
    "earns its place by referencing this player's real data.\n\n"
    "You are given ONLY real measured numbers for one swing (or session): the "
    "player's metrics with their own recent baseline, the matched launch-monitor "
    "shot, and reputable ideal/tour ranges where they exist. The grounding "
    "discipline is absolute and overrides your fluency:\n"
    "(1) Every finding MUST cite one of the provided metrics by its exact name "
    "and value. (2) Never invent metrics, numbers, or ideal/tour ranges that are "
    "not present in the context -- not even ones you 'know' from experience. "
    "(3) Compare each finding to the player's baseline and/or the provided ideal "
    "range. (4) For metrics flagged history-only or low confidence, say so "
    "plainly and temper your certainty accordingly. (5) Tie findings to the ball "
    "result when the shot is present. "
    "\n\nOUTPUT FOR DISPLAY -- the player only ever sees two fields, so make "
    "them count:\n"
    "- 'headline': ONE short plain-language sentence verdict on this swing "
    "(e.g. 'What you've got today is solid, but the face is leaking right'). No "
    "raw numbers, no jargon.\n"
    "- 'summary': a HARD MAXIMUM of 3 short sentences naming ONLY the top two "
    "or three 'worst-offender' metrics -- the ones furthest from their "
    "ideal/tour range or most responsible for the ball result. For each, say in "
    "plain words what it is doing, why it matters (cause and effect), and how it "
    "shows up in the ball flight. Put NO numeric values in the summary at all -- "
    "no degrees, mph, rpm, or inches, and no parenthetical figures. Describe "
    "magnitude in words instead ('a touch steep', 'well above tour', 'nearly "
    "square'); the exact numbers already sit on the cards beside this read. Do "
    "not walk through every metric. If nothing is meaningfully off, say so in "
    "one sentence. Keep it tight and skimmable.\n"
    "The 'findings'/'drills' arrays are internal grounding (not shown to the "
    "player); still fill them honestly so the headline and summary stay anchored "
    "to real measured numbers.\n"
    "Output STRICT JSON only."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["headline", "findings", "drills", "confidence_notes"],
    "properties": {
        "headline": {"type": "string"},
        # Optional 2-4 sentence expert narrative read of the swing. Free prose;
        # not validated for grounding (the bullet `findings` carry that burden),
        # but the SYSTEM prompt instructs it to stay tied to the given numbers.
        "summary": {"type": ["string", "null"]},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["metric", "value"],
                "properties": {
                    "metric": {"type": "string"},
                    "context": {"type": ["string", "null"]},
                    "value": {"type": "number"},
                    "unit": {"type": ["string", "null"]},
                    "vs_baseline": {"type": ["string", "null"]},
                    "vs_ideal": {"type": ["string", "null"]},
                    "ball_effect": {"type": ["string", "null"]},
                    "severity": {"type": ["string", "null"]},
                },
            },
        },
        "drills": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["name"],
                "properties": {
                    "name": {"type": "string"},
                    "why": {"type": ["string", "null"]},
                    "how": {"type": ["string", "null"]},
                },
            },
        },
        "confidence_notes": {"type": "array", "items": {"type": "string"}},
    },
}


def _iter_context_metrics(context):
    """Yield every metric dict from a swing or session context."""
    if context.get("kind") == "session":
        for sw in context.get("swings", []):
            yield from sw.get("metrics", [])
    else:
        yield from context.get("metrics", [])


def build_user(context):
    """Render the grounding context as the user prompt (real numbers only)."""
    return (
        "Here is the grounding context for this "
        f"{context.get('kind', 'swing')}. Use ONLY these numbers:\n\n"
        + json.dumps(context, indent=2, sort_keys=True)
        + "\n\nReturn JSON with keys: headline (ONE short plain-language "
        "verdict sentence), summary (2-3 tight sentences calling out only the "
        "top two or three worst-offender metrics and how they show up in the "
        "ball flight -- no raw numbers, the player sees those on the cards), "
        "findings[] (internal grounding: the measured deltas), drills[], and "
        "confidence_notes[]. Each finding must cite one metric above by exact "
        "name and value and compare to baseline and/or ideal."
    )


def validate(obj, context):
    """Return (ok, errors). Rejects malformed or ungrounded output."""
    errors = []
    if not isinstance(obj, dict):
        return False, ["output is not a JSON object"]

    for key in OUTPUT_SCHEMA["required"]:
        if key not in obj:
            errors.append(f"missing required key: {key}")
    if errors:
        return False, errors

    # `summary` is optional, but if present it must be a string (free prose;
    # its grounding is governed by the SYSTEM prompt, not enforced here -- the
    # findings checks below remain the hard anti-hallucination gate).
    if "summary" in obj and obj["summary"] is not None \
            and not isinstance(obj["summary"], str):
        errors.append("summary must be a string when present")

    if not isinstance(obj["findings"], list):
        return False, errors + ["findings must be a list"]
    if not isinstance(obj["drills"], list):
        errors.append("drills must be a list")
    if not isinstance(obj["confidence_notes"], list):
        errors.append("confidence_notes must be a list")

    # Index real metrics by (name, context) -> set of allowed (rounded) values.
    # Keying by NAME ALONE would let a finding cite a value that only exists in a
    # DIFFERENT phase (e.g. hip_sway_in @ top vs @ impact), so the grounding key
    # is the (metric, context) pair the metric was actually measured in.
    by_key = {}
    for m in _iter_context_metrics(context):
        key = (m["name"], m.get("context"))
        by_key.setdefault(key, set()).add(
            round(m["value"], 6) if m.get("value") is not None else None)
    known_names = {name for (name, _ctx) in by_key}

    # The matched launch-monitor shot is ALSO a grounded source: the coach is
    # told to tie findings to the ball result, so a finding may cite a ball/club
    # field (e.g. club_speed, attack_angle, carry) by name. Its value must match
    # the real shot value (anti-hallucination preserved). Ball facts carry no
    # per-metric baseline/ideal, so they are exempt from the comparison rule.
    shot = context.get("shot") or {}
    shot_vals = {k: round(float(v), 6) for k, v in shot.items()
                 if k != "id" and isinstance(v, (int, float))}

    for i, f in enumerate(obj["findings"]):
        if not isinstance(f, dict):
            errors.append(f"finding {i} is not an object")
            continue
        name = f.get("metric")
        val = f.get("value")
        if name in known_names:
            key = (name, f.get("context"))
            allowed = by_key.get(key)
            if allowed is None:
                errors.append(
                    f"finding {i} cites metric {name!r} in unknown context "
                    f"{f.get('context')!r}")
                continue
            if val is None or round(float(val), 6) not in allowed:
                errors.append(
                    f"finding {i} value {val!r} does not match metric {name!r} "
                    f"in context {f.get('context')!r}")
            if not (f.get("vs_baseline") or f.get("vs_ideal")):
                errors.append(
                    f"finding {i} has no comparison (vs_baseline/vs_ideal)")
        elif name in shot_vals:
            if val is None or round(float(val), 6) != shot_vals[name]:
                errors.append(
                    f"finding {i} value {val!r} does not match shot field "
                    f"{name!r} ({shot_vals[name]})")
        else:
            errors.append(f"finding {i} cites unknown metric: {name!r}")

    return (len(errors) == 0), errors
