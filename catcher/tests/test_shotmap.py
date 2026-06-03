import json
from catcher.shotmap import map_message, is_heartbeat
from store.models import Shot


SHOT_MSG = {
    "DeviceID": "GARMIN-R50",
    "Units": "Yards",
    "ShotNumber": 7,
    "APIversion": "1",
    "BallData": {
        "Speed": 148.2,
        "SpinAxis": -6.4,
        "TotalSpin": 2710.0,
        "HLA": 1.2,
        "VLA": 13.8,
        "CarryDistance": 232.5,
    },
    "ClubData": {
        "Speed": 102.1,
        "AngleOfAttack": -2.3,
        "Path": 2.1,
        "FaceToTarget": -0.7,
    },
    "ShotDataOptions": {
        "ContainsBallData": True,
        "ContainsClubData": True,
        "IsHeartBeat": False,
    },
}

HEARTBEAT_MSG = {
    "DeviceID": "GARMIN-R50",
    "ShotDataOptions": {
        "ContainsBallData": False,
        "ContainsClubData": False,
        "IsHeartBeat": True,
    },
}


def test_heartbeat_maps_to_none():
    assert is_heartbeat(HEARTBEAT_MSG) is True
    assert map_message(HEARTBEAT_MSG) is None


def test_shot_maps_all_fields():
    shot = map_message(SHOT_MSG)
    assert isinstance(shot, Shot)
    assert shot.device_id == "GARMIN-R50"
    assert shot.shot_number == 7
    assert shot.ball_speed == 148.2
    assert shot.total_spin == 2710.0
    assert shot.spin_axis == -6.4
    assert shot.hla == 1.2
    assert shot.vla == 13.8
    assert shot.carry == 232.5
    assert shot.club_speed == 102.1
    assert shot.attack_angle == -2.3
    assert shot.club_path == 2.1
    assert shot.face_to_target == -0.7
    # captured_at is a populated ISO-8601 string
    assert isinstance(shot.captured_at, str) and "T" in shot.captured_at
    # player/session not assigned by the mapper (sessionmgr does that)
    assert shot.player_id is None and shot.session_id is None
    # raw_json round-trips to the original message
    assert json.loads(shot.raw_json) == SHOT_MSG


def test_shot_ball_only_when_no_club():
    msg = {
        "DeviceID": "R50",
        "ShotNumber": 1,
        "BallData": {"Speed": 100.0, "VLA": 12.0, "TotalSpin": 3000.0},
        "ShotDataOptions": {"ContainsBallData": True, "ContainsClubData": False,
                            "IsHeartBeat": False},
    }
    shot = map_message(msg)
    assert shot is not None
    assert shot.ball_speed == 100.0
    assert shot.club_speed is None  # no club data present
    assert shot.club_path is None


def test_missing_shotdataoptions_is_treated_as_shot():
    # be tolerant: a message with BallData but no ShotDataOptions is still a shot
    msg = {"DeviceID": "R50", "ShotNumber": 2, "BallData": {"Speed": 90.0}}
    shot = map_message(msg)
    assert shot is not None and shot.ball_speed == 90.0
