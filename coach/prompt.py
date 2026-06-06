"""System/user prompt templates, the strict JSON output schema, and validate().

validate() is the anti-generic gate: every finding must cite a metric that
actually appears in the grounding context, with a matching value, and must
compare to baseline and/or ideal. Malformed output is rejected (never stored).
"""
import json

SYSTEM = (
    "You are a precise golf swing coach. You are given ONLY real measured "
    "numbers for one swing (or session): the player's metrics with their own "
    "recent baseline, the matched launch-monitor shot, and reputable ideal "
    "ranges where they exist. Rules: (1) Every finding MUST cite one of the "
    "provided metrics by its exact name and value. (2) Never invent metrics, "
    "numbers, or ideal ranges not present in the context. (3) Compare each "
    "finding to the player's baseline and/or the provided ideal range. (4) For "
    "metrics flagged history-only or low confidence, say so plainly. (5) Tie "
    "findings to the ball result when the shot is present. Be specific and "
    "concise. Output STRICT JSON only."
)

OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["headline", "findings", "drills", "confidence_notes"],
    "properties": {
        "headline": {"type": "string"},
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
        + "\n\nReturn JSON with keys: headline, findings[], drills[], "
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

    if not isinstance(obj["findings"], list):
        return False, ["findings must be a list"]
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
