"""Pure mapping from GSPro Open Connect JSON messages to store.models.Shot.

No I/O, no DB, no tkinter. Distinguishes shots from heartbeats. Stores whatever
ball/club fields arrive plus the full original message in raw_json; no field is
assumed mandatory (a monitor may send ball-only or include club data).

Two wire quirks are normalized here so the rest of the app never sees a fake
number:
  * ShotDataOptions.ContainsClubData == False -> the ClubData block is padding
    and is ignored wholesale.
  * Devices that pad absent numerics with 0.0 (see catcher.trust device
    profiles) have those specific zeros mapped to None. Permissive devices such
    as the R50 keep their zeros, because a measured angle can legitimately be 0.
"""
import json
from typing import Optional

from store import db as dbmod
from store.models import Shot
from catcher import trust


def is_heartbeat(obj: dict) -> bool:
    sdo = obj.get("ShotDataOptions") or {}
    return bool(sdo.get("IsHeartBeat"))


def _num(d: dict, key):
    v = d.get(key)
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def map_message(obj: dict) -> Optional[Shot]:
    """Return a Shot for a shot message, or None for a heartbeat.

    captured_at is stamped now (UTC ISO-8601); player_id / session_id are left
    None for the SessionManager to assign.
    """
    if is_heartbeat(obj):
        return None

    device_id = obj.get("DeviceID")
    profile = trust.profile_for(device_id)

    ball = obj.get("BallData") or {}
    sdo = obj.get("ShotDataOptions") or {}
    # Absent flag means "legacy device, trust the block" (the R50 sends no flag).
    club = obj.get("ClubData") or {}
    if sdo.get("ContainsClubData") is False:
        club = {}

    shot_number = obj.get("ShotNumber")
    if shot_number is not None:
        try:
            shot_number = int(shot_number)
        except (TypeError, ValueError):
            shot_number = None

    def field(value, name):
        """Null out a padded zero for devices known to pad that field."""
        if value == 0.0 and name in profile.zero_means_absent:
            return None
        return value

    return Shot(
        captured_at=dbmod.now_iso(),
        device_id=device_id,
        shot_number=shot_number,
        ball_speed=_num(ball, "Speed"),
        total_spin=_num(ball, "TotalSpin"),
        spin_axis=field(_num(ball, "SpinAxis"), "spin_axis"),
        hla=field(_num(ball, "HLA"), "hla"),
        vla=_num(ball, "VLA"),
        carry=_num(ball, "CarryDistance"),
        club_speed=_num(club, "Speed"),
        attack_angle=field(_num(club, "AngleOfAttack"), "attack_angle"),
        club_path=_num(club, "Path"),
        face_to_target=field(_num(club, "FaceToTarget"), "face_to_target"),
        raw_json=json.dumps(obj),
    )
