from web.backend.capture import CaptureEventBus


def test_publish_then_drain_returns_events_in_order():
    bus = CaptureEventBus()
    bus.publish("capture_status", {"status": "connected"})
    bus.publish("shot_received", {"shot_id": 5, "player_id": 1})
    drained = bus.drain()
    assert [e["event"] for e in drained] == ["capture_status", "shot_received"]
    assert drained[1]["data"] == {"shot_id": 5, "player_id": 1}


def test_drain_is_idempotent_clears_buffer():
    bus = CaptureEventBus()
    bus.publish("capture_status", {"status": "paused"})
    assert len(bus.drain()) == 1
    assert bus.drain() == []  # already consumed


def test_drain_is_thread_safe_under_concurrent_publish():
    import threading
    bus = CaptureEventBus()

    def producer():
        for i in range(100):
            bus.publish("shot_received", {"i": i})

    threads = [threading.Thread(target=producer) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    # all 400 events must be drainable exactly once, no loss/crash
    assert len(bus.drain()) == 400
