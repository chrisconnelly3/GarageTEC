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
    "Write the optional 'summary' as 2-4 sentences of expert read -- the kind of "
    "verbal diagnosis you'd give standing next to the player -- but it too may "
    "only lean on the numbers you were given. Be specific, vivid, and concise. "
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
        + "\n\nReturn JSON with keys: headline (a concise one-line verdict), "
        "summary (2-4 sentences: your expert read of impact position, "
        "sequencing, and the resulting ball flight, grounded in the numbers "
        "above), findings[] (the quick measured deltas), drills[], and "
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

    for i, f in enumerate(obj["findings"]):
        if not isinstance(f, dict):
            errors.append(f"finding {i} is not an object")
            continue
        name = f.get("metric")
        if name not in known_names:
            errors.append(f"finding {i} cites unknown metric: {name!r}")
            continue
        key = (name, f.get("context"))
        allowed = by_key.get(key)
        if allowed is None:
            errors.append(
                f"finding {i} cites metric {name!r} in unknown context "
                f"{f.get('context')!r}")
            continue
        val = f.get("value")
        if val is None or round(float(val), 6) not in allowed:
            errors.append(
                f"finding {i} value {val!r} does not match metric {name!r} "
                f"in context {f.get('context')!r}")
        if not (f.get("vs_baseline") or f.get("vs_ideal")):
            errors.append(
                f"finding {i} has no comparison (vs_baseline/vs_ideal)")

    return (len(errors) == 0), errors
