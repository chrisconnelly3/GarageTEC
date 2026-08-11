from catcher.enrich_buffer import EnrichBuffer


def test_enrichment_first_then_shot_matches():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.2) == {"ball_speed_mph": 148.2}


def test_match_is_claimed_only_once():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.2) is not None
    assert buf.take_for(148.2) is None


def test_speed_mismatch_does_not_match():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(150.0) is None


def test_stale_records_expire():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0], window_s=5.0)
    buf.add_enrichment({"ball_speed_mph": 148.2})
    clock[0] = 1006.0
    assert buf.take_for(148.2) is None


def test_duplicate_speeds_are_matched_first_in_first_out():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2, "n": 1})
    buf.add_enrichment({"ball_speed_mph": 148.2, "n": 2})
    assert buf.take_for(148.2)["n"] == 1
    assert buf.take_for(148.2)["n"] == 2


def test_rounding_tolerance():
    """Both channels round to 1dp, but tolerate float noise anyway."""
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"ball_speed_mph": 148.2})
    assert buf.take_for(148.24) is not None


def test_missing_ball_speed_is_ignored():
    clock = [1000.0]
    buf = EnrichBuffer(now=lambda: clock[0])
    buf.add_enrichment({"no_speed": True})
    assert buf.take_for(148.2) is None
