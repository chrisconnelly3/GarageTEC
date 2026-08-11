from catcher.openflight_enrich import normalize_event, url_for_host


FULL_EVENT = {
    "shot": {
        "ball_speed_mph": 148.2,
        "club_speed_mph": 102.1,
        "estimated_carry_yards": 232,
        "launch_angle_vertical": 13.8,
        "launch_angle_vertical_confidence": 0.92,
        "spin_rpm": 2710,
        "spin_rpm_measured": 2710,
    },
    "stats": {"shot_count": 4},
}


def test_normalize_extracts_inner_shot():
    assert normalize_event(FULL_EVENT)["ball_speed_mph"] == 148.2


def test_normalize_accepts_bare_shot_dict():
    """Tolerate the payload arriving unwrapped."""
    assert normalize_event(FULL_EVENT["shot"])["ball_speed_mph"] == 148.2


def test_normalize_rejects_non_dict():
    assert normalize_event(None) is None
    assert normalize_event([1, 2, 3]) is None
    assert normalize_event("shot") is None


def test_normalize_rejects_shot_without_ball_speed():
    assert normalize_event({"shot": {"club_speed_mph": 90.0}}) is None


def test_schema_drift_keeps_what_it_can():
    """Renamed/removed keys must not crash; ball speed is the only requirement."""
    drifted = {"shot": {"ball_speed_mph": 100.0, "launch_angle_v2": 12.0}}
    out = normalize_event(drifted)
    assert out["ball_speed_mph"] == 100.0
    assert "launch_angle_v2" in out


def test_url_for_host_defaults_to_openflight_port():
    assert url_for_host("192.168.1.50") == "http://192.168.1.50:8080"


def test_url_for_host_accepts_explicit_port():
    assert url_for_host("192.168.1.50", 9000) == "http://192.168.1.50:9000"


def test_missing_dependency_reports_unavailable(monkeypatch):
    """The optional dep is absent: degrade, never raise."""
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "socketio":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    from catcher.openflight_enrich import OpenFlightEnrichClient
    states = []
    client = OpenFlightEnrichClient("127.0.0.1",
                                    on_status=lambda s, d: states.append(s))
    client._run()                      # direct call, no thread
    assert states == ["unavailable"]
    assert client.is_connected() is False


def test_shot_event_forwards_normalized_record(monkeypatch):
    """A fake socketio client proves the shot handler wiring and filtering."""
    import sys
    import types

    handlers = {}

    class FakeClient:
        def __init__(self, **kwargs):
            self.connected = False

        def event(self, fn):                      # @sio.event
            handlers[fn.__name__] = fn
            return fn

        def on(self, name):                       # @sio.on("shot")
            def deco(fn):
                handlers[name] = fn
                return fn
            return deco

        def connect(self, url, **kwargs):
            self.connected = True

        def wait(self):
            pass

        def disconnect(self):
            self.connected = False

    fake_module = types.ModuleType("socketio")
    fake_module.Client = FakeClient
    monkeypatch.setitem(sys.modules, "socketio", fake_module)

    from catcher.openflight_enrich import OpenFlightEnrichClient
    got = []
    client = OpenFlightEnrichClient("127.0.0.1", on_enrichment=got.append)
    client._run()

    handlers["shot"]({"shot": {"ball_speed_mph": 148.2}})
    handlers["shot"]({"shot": {"club_speed_mph": 90.0}})   # no ball speed -> ignored
    handlers["shot"]("garbage")                             # unusable -> ignored

    assert [r["ball_speed_mph"] for r in got] == [148.2]
