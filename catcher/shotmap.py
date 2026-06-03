"""Pure mapping from GSPro Open Connect JSON messages to store.models.Shot.

No I/O, no DB, no tkinter. Distinguishes shots from heartbeats. Stores whatever
ball/club fields arrive plus the full original message in raw_json; no field is
assumed mandatory (the R50 may send ball-only or include club data).
"""
import json
from typing import Optional

from store import db as dbmod
from store.models import Shot


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

    ball = obj.get("BallData") or {}
    club = obj.get("ClubData") or {}

    shot_number = obj.get("ShotNumber")
    if shot_number is not None:
        try:
            shot_number = int(shot_number)
        except (TypeError, ValueError):
            shot_number = None

    return Shot(
        captured_at=dbmod.now_iso(),
        device_id=obj.get("DeviceID"),
        shot_number=shot_number,
        ball_speed=_num(ball, "Speed"),
        total_spin=_num(ball, "TotalSpin"),
        spin_axis=_num(ball, "SpinAxis"),
        hla=_num(ball, "HLA"),
        vla=_num(ball, "VLA"),
        carry=_num(ball, "CarryDistance"),
        club_speed=_num(club, "Speed"),
        attack_angle=_num(club, "AngleOfAttack"),
        club_path=_num(club, "Path"),
        face_to_target=_num(club, "FaceToTarget"),
        raw_json=json.dumps(obj),
    )
