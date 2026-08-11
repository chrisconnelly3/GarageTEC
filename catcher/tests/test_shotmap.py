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


OPENFLIGHT_MSG = {
    "DeviceID": "OpenFlight",
    "Units": "Yards",
    "ShotNumber": 3,
    "APIversion": "1",
    "BallData": {
        "Speed": 121.4, "SpinAxis": 0.0, "TotalSpin": 7000.0,
        "BackSpin": 7000.0, "SideSpin": 0.0, "HLA": 0.0, "VLA": 16.3,
        "CarryDistance": 171.0,
    },
    # OpenFlight always sends the block, padding unset numbers with 0.0.
    "ClubData": {
        "Speed": 0.0, "AngleOfAttack": 0.0, "FaceToTarget": 0.0, "Path": 2.1,
    },
    "ShotDataOptions": {
        "ContainsBallData": True,
        "ContainsClubData": False,
        "LaunchMonitorIsReady": True,
        "LaunchMonitorBallDetected": True,
        "IsHeartBeat": False,
    },
}


def test_club_data_ignored_when_flag_false():
    shot = map_message(OPENFLIGHT_MSG)
    assert shot.club_speed is None
    assert shot.attack_angle is None
    assert shot.face_to_target is None
    assert shot.club_path is None


def test_openflight_zeros_become_none():
    shot = map_message(OPENFLIGHT_MSG)
    assert shot.hla is None
    assert shot.spin_axis is None
    # Real measurements are untouched.
    assert shot.ball_speed == 121.4
    assert shot.vla == 16.3
    assert shot.carry == 171.0


def test_r50_zeros_are_preserved():
    """Regression: a measured zero from a permissive device stays 0.0."""
    msg = json.loads(json.dumps(SHOT_MSG))
    msg["BallData"]["HLA"] = 0.0
    msg["BallData"]["SpinAxis"] = 0.0
    shot = map_message(msg)
    assert shot.hla == 0.0
    assert shot.spin_axis == 0.0


def test_r50_club_data_still_read():
    """Regression: the R50 sends no ContainsClubData flag; keep reading club data."""
    shot = map_message(SHOT_MSG)
    assert shot.club_speed == 102.1
    assert shot.attack_angle == -2.3
