"""Per-field trust policy for incoming launch-monitor shots.

Pure: no I/O, no DB, no network. Given an OpenFlight enrichment record (or None),
decide for each GarageTEC shot field whether the number was actually MEASURED,
is a model-derived ESTIMATE, or is ABSENT. Callers use the tier to decide whether
to grade a value against tour averages, badge it in the UI, or hide it.

Also owns the per-device profile that says which literal 0.0 values on the
OpenConnect wire mean "no measurement" (see `zero_means_absent`).
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

MEASURED = "measured"
ESTIMATED = "estimated"
ABSENT = "absent"

# Mirrors OpenFlight's own SPIN_CONFIDENCE_HIGH (src/openflight/launch_monitor.py:17),
# the bar it uses internally before accepting a spin reading. Tune here only.
CONFIDENCE_MIN = 0.7

# Substrings that mark a source as model-derived. Matching is defensive: an
# UNRECOGNIZED source never forces ESTIMATED on its own (confidence still decides),
# so a renamed source string upstream degrades gracefully instead of mislabeling.
ESTIMATE_SOURCE_MARKERS = ("model", "estimate", "fallback", "default")


@dataclass(frozen=True)
class DeviceProfile:
    """Per-device wire quirks.

    zero_means_absent: fields where a literal 0.0 on the OpenConnect wire means
    "no measurement" rather than a real zero. Only ever populated for devices
    that pad absent fields with 0.0. Empty for the R50 and anything unknown,
    because a measured HLA/spin-axis/attack-angle can legitimately BE zero.

    fabricates_unmeasured: True when the device substitutes plausible values
    for fields it cannot actually measure. For such a device, a shot with no
    per-field provenance record (no enrichment) cannot be trusted beyond its
    guaranteed outputs. False for devices that only ever report what they
    measured (nulls come through as NULL, not a guess).
    """
    zero_means_absent: frozenset = field(default_factory=frozenset)
    fabricates_unmeasured: bool = False


# OpenFlight's GSPro codec always emits a ClubData block and defaults unset
# numeric fields to 0.0. AngleOfAttack and FaceToTarget are never assigned at
# all; HLA and SpinAxis are set to 0.0 by its resolver when unmeasured.
OPENFLIGHT_PROFILE = DeviceProfile(
    zero_means_absent=frozenset({"hla", "spin_axis", "attack_angle", "face_to_target"}),
    fabricates_unmeasured=True,
)
PERMISSIVE_PROFILE = DeviceProfile()

DEVICE_PROFILES: Dict[str, DeviceProfile] = {
    "OpenFlight": OPENFLIGHT_PROFILE,
}


def profile_for(device_id: Optional[str]) -> DeviceProfile:
    """Profile for a DeviceID. Unknown devices get the permissive profile."""
    return DEVICE_PROFILES.get(device_id or "", PERMISSIVE_PROFILE)


def _num(value):
    """Coerce to float, or None when missing/unparseable."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _tier(value, *, source=None, confidence=None, conf_required=False) -> str:
    if _num(value) is None:
        return ABSENT
    if source is not None:
        text = str(source).lower()
        if any(marker in text for marker in ESTIMATE_SOURCE_MARKERS):
            return ESTIMATED
    conf = _num(confidence)
    if conf is None:
        # Fields that ship a confidence score on the wire must produce one. A
        # missing score is unverifiable, so fail safe rather than grade a value
        # we cannot vouch for.
        return ESTIMATED if conf_required else MEASURED
    if conf < CONFIDENCE_MIN:
        return ESTIMATED
    return MEASURED


# Tiers used when no enrichment record arrived, for a device that fabricates
# values it cannot measure (OpenFlight). Ball speed and carry are the
# monitor's load-bearing outputs and are always sent; anything OpenFlight may
# have substituted is treated as an estimate rather than graded as fact.
_NO_ENRICHMENT = {
    "ball_speed": MEASURED,
    "carry": MEASURED,
    "club_speed": MEASURED,
    "vla": ESTIMATED,
    "hla": ESTIMATED,
    "total_spin": ESTIMATED,
    "back_spin": ESTIMATED,
    "side_spin": ESTIMATED,
    "spin_axis": ESTIMATED,
    "club_path": ESTIMATED,
    "attack_angle": ABSENT,
    "face_to_target": ABSENT,
}

# Tiers used when no enrichment record arrived, for a device that only
# reports what it actually measured (the R50, and anything without a
# fabricating profile). Absent values arrive as NULL and are handled by the
# existing null/"--" display path, so every field it does send is trustworthy.
_TRUSTED = {field: MEASURED for field in _NO_ENRICHMENT}


def derive_tiers(enrichment: Optional[dict], device_id: Optional[str] = None) -> Dict[str, str]:
    """Map each GarageTEC shot field to MEASURED / ESTIMATED / ABSENT.

    `enrichment` is the inner "shot" dict of OpenFlight's Socket.IO event, or
    None when no enrichment was correlated. Every lookup is defensive so a
    renamed or removed upstream key degrades one field instead of raising.

    Without an enrichment record, the right fallback depends on the device:
    a device that fabricates values for fields it cannot measure (see
    `DeviceProfile.fabricates_unmeasured`) gives us no way to tell a guess
    from real data, so we fall back to the conservative `_NO_ENRICHMENT` map.
    A device that only ever reports what it measured (the R50 is the primary
    example, and it's the default for unknown devices) can be trusted outright
    -- unmeasured fields simply arrive as NULL -- so it gets `_TRUSTED`.
    """
    if not enrichment:
        if profile_for(device_id).fabricates_unmeasured:
            return dict(_NO_ENRICHMENT)
        return dict(_TRUSTED)

    e = enrichment
    tiers: Dict[str, str] = {}

    tiers["ball_speed"] = _tier(e.get("ball_speed_mph"))
    tiers["club_speed"] = _tier(e.get("club_speed_mph"))
    tiers["spin_axis"] = _tier(e.get("spin_axis_deg"))

    tiers["vla"] = _tier(
        e.get("launch_angle_vertical"),
        source=e.get("launch_angle_vertical_source"),
        confidence=e.get("launch_angle_vertical_confidence"),
        conf_required=True,
    )
    tiers["hla"] = _tier(
        e.get("launch_angle_horizontal"),
        source=e.get("launch_angle_horizontal_source"),
        confidence=e.get("launch_angle_horizontal_confidence"),
        conf_required=True,
    )

    # Spin: OpenFlight exposes both the final value and the raw measurement.
    # A final value with no measured twin is the per-club model -> ESTIMATED.
    # This is a structural signal, so it survives source-string renames.
    spin_tier = _tier(
        e.get("spin_rpm"),
        source=e.get("spin_source"),
        confidence=e.get("spin_confidence"),
        conf_required=True,
    )
    if spin_tier != ABSENT and _num(e.get("spin_rpm_measured")) is None:
        spin_tier = ESTIMATED
    tiers["total_spin"] = spin_tier
    # Back/side spin are trigonometric derivations of total spin and its axis.
    tiers["back_spin"] = spin_tier
    tiers["side_spin"] = spin_tier

    # Carry is never directly observed: it is a ballistic model output, so it is
    # only as trustworthy as the launch angle that drove it.
    tiers["carry"] = (
        ABSENT if _num(e.get("estimated_carry_yards")) is None else tiers["vla"]
    )

    # OpenFlight documents club path as experimental.
    tiers["club_path"] = (
        ABSENT if _num(e.get("club_path_deg")) is None else ESTIMATED
    )

    # Never produced by OpenFlight's GSPro codec.
    tiers["attack_angle"] = ABSENT
    tiers["face_to_target"] = ABSENT

    return tiers
