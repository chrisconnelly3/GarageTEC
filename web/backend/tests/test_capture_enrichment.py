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


class _FakeEnrichClient:
    """No-socket stand-in for OpenFlightEnrichClient. A real six of these seven
    tests trigger note_source(), which starts a client; without this injection
    seam they'd each open a real Socket.IO connection attempt to a plausible
    LAN address and leak a reconnecting thread for the rest of the pytest run."""
    def __init__(self, host, **kw):
        self.host = host
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def is_connected(self):
        return False


def _supervisor(conn):
    sup = CaptureSupervisor(conn=conn, bus=CaptureEventBus(),
                            listener_factory=lambda **kw: None,
                            enrich_client_factory=_FakeEnrichClient)
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


def test_enrichment_arriving_during_the_insert_is_not_lost(conn):
    """Regression: the take_for/_note_recent_shot window (FIX 1)."""
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    real_save = sup.persister.save

    def save_with_enrichment_midflight(c, s):
        sup.on_enrichment({"ball_speed_mph": 148.2, "spin_rpm_measured": 2710})
        return real_save(c, s)

    sup.persister.save = save_with_enrichment_midflight
    saved = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    stored = repo.get_shot(conn, saved.id)
    assert stored.enrichment_json is not None, "enrichment lost in the insert window"
    assert json.loads(stored.enrichment_json)["spin_rpm_measured"] == 2710


def test_late_enrichments_pair_in_shot_order(conn):
    """Regression: FIFO pairing, not LIFO (FIX 2)."""
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    first = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")
    second = sup.handle_message(dict(OPENFLIGHT_MSG, ShotNumber=2),
                               source="192.168.1.50:54321")
    assert first.id != second.id

    sup.on_enrichment({"ball_speed_mph": 148.2, "tag": "for_first"})
    sup.on_enrichment({"ball_speed_mph": 148.2, "tag": "for_second"})

    assert json.loads(repo.get_shot(conn, first.id).enrichment_json)["tag"] == "for_first"
    assert json.loads(repo.get_shot(conn, second.id).enrichment_json)["tag"] == "for_second"


def test_failed_enrichment_write_does_not_drift_to_another_shot(conn, monkeypatch):
    """Regression: a write failure forfeits the record, never re-buffers it (FIX 3)."""
    player = seed_player(conn)
    sup = _supervisor(conn)
    sup.set_active_player(player.name, player.height_in, player.handedness)
    sup.start_session()

    first = sup.handle_message(OPENFLIGHT_MSG, source="192.168.1.50:54321")

    def boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    monkeypatch.setattr(repo, "set_shot_enrichment", boom)
    sup.on_enrichment({"ball_speed_mph": 148.2, "tag": "doomed"})
    monkeypatch.undo()

    second = sup.handle_message(dict(OPENFLIGHT_MSG, ShotNumber=2),
                               source="192.168.1.50:54321")
    assert repo.get_shot(conn, second.id).enrichment_json is None, \
        "forfeited record drifted onto a later shot"
