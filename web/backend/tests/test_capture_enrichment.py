import json

from web.backend.capture import CaptureSupervisor, CaptureEventBus
from web.backend.tests.conftest import seed_player
from store import repo


OPENFLIGHT_MSG = {
    "DeviceID": "OpenFlight",
    "ShotNumber": 1,
    "BallData": {"Speed": 148.2, "VLA": 13.8, "CarryDistance": 232.0,
                 "TotalSpin": 2710.0, "HLA": 0.0, "SpinAxis": 0.0},
    "ClubData": {"Speed": 0.0, "AngleOfAttack": 0.0, "FaceToTarget": 0.0,
                 "Path": 2.1},
    "ShotDataOptions": {"ContainsClubData": False, "IsHeartBeat": False},
}


def _supervisor(conn):
    sup = CaptureSupervisor(conn=conn, bus=CaptureEventBus(),
                            listener_factory=lambda **kw: None)
    return sup


def test_enrichment_is_attached_to_the_shot(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    # Enrichment arrives first, as it does in practice (same physical shot).
    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 2710,
                       "spin_rpm_measured": 2710})
    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    assert saved is not None
    stored = repo.get_shot(conn, saved.id)
    assert json.loads(stored.enrichment_json)["spin_rpm_measured"] == 2710


def test_enrichment_arriving_after_the_shot_is_attached(conn):
    """The two channels race: handle the shot-first ordering too."""
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    assert repo.get_shot(conn, saved.id).enrichment_json is None

    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 2710,
                       "spin_rpm_measured": 2710})

    stored = repo.get_shot(conn, saved.id)
    assert json.loads(stored.enrichment_json)["spin_rpm_measured"] == 2710


def test_late_enrichment_matches_only_one_shot(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    # Two genuinely distinct shots that happen to share a ball speed. They must
    # differ in ShotNumber, or repo.save_shot's content-derived dedupe_key makes
    # the second resolve to the same row (crash-replay idempotency by design).
    first = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    second_msg = dict(OPENFLIGHT_MSG, ShotNumber=2)
    second = sup.handle_message(second_msg, source="192.168.1.50:54321")
    assert first.id != second.id, "fixture must produce two distinct rows"

    sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm": 1})

    enriched = [s for s in (first, second)
                if repo.get_shot(conn, s.id).enrichment_json is not None]
    assert len(enriched) == 1


def test_shot_persists_without_enrichment(conn):
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    assert saved is not None
    assert repo.get_shot(conn, saved.id).enrichment_json is None


def test_openflight_host_learned_from_connection_source(conn):
    sup = _supervisor(conn)
    assert sup.openflight_host is None
    sup.note_source("OpenFlight", "192.168.1.50:54321")
    assert sup.openflight_host == "192.168.1.50"


def test_non_openflight_device_does_not_set_host(conn):
    sup = _supervisor(conn)
    sup.note_source("GARMIN-R50", "192.168.1.77:5000")
    assert sup.openflight_host is None


def test_probe_style_source_is_parsed(conn):
    sup = _supervisor(conn)
    sup.note_source("OpenFlight", "PROBE->192.168.1.50:921")
    assert sup.openflight_host == "192.168.1.50"
