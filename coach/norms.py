import json
import os

_DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "norms", "norms.json")
_RESERVED = {"_meta"}


def load_norms(path=None):
    with open(path or _DEFAULT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _history_only(entry):
    return {
        "in_range": None,
        "delta": None,
        "direction": None,
        "source": (entry or {}).get("source"),
        "confidence": "none",
        "use_history_only": True,
    }


def compare(name, value, club=None, norms=None):
    """Compare `value` to the ideal range for `name`.

    Returns a dict: in_range (bool|None), delta (float|None, signed distance
    outside the range; 0.0 if inside), direction ('above'|'below'|None),
    source, confidence, use_history_only.
    Unknown metrics and confidence:'none' entries return a history-only result.
    """
    norms = load_norms() if norms is None else norms
    entry = norms.get(name)
    if entry is None or name in _RESERVED:
        return _history_only(None)

    confidence = entry.get("confidence", "none")
    rng = entry.get("range") or []
    if confidence == "none" or len(rng) != 2 or value is None:
        return _history_only(entry)

    low, high = float(rng[0]), float(rng[1])
    if value < low:
        in_range, delta, direction = False, value - low, "below"
    elif value > high:
        in_range, delta, direction = False, value - high, "above"
    else:
        in_range, delta, direction = True, 0.0, None
    return {
        "in_range": in_range,
        "delta": delta,
        "direction": direction,
        "source": entry.get("source"),
        "confidence": confidence,
        "use_history_only": False,
    }
