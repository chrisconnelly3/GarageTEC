import pytest

from coach import backend as bk


def test_fake_backend_returns_canned_dict():
    canned = {"headline": "ok", "findings": [], "drills": [],
              "confidence_notes": []}
    fb = bk.FakeBackend(canned)
    out = fb.complete("sys", "user", {"type": "object"})
    assert out == canned
    assert fb.calls == [("sys", "user", {"type": "object"})]


def test_fake_backend_can_raise():
    fb = bk.FakeBackend(error=RuntimeError("boom"))
    with pytest.raises(RuntimeError):
        fb.complete("s", "u", {})


def test_make_backend_selects_fake():
    fb = bk.make_backend("fake", canned={"headline": "hi"})
    assert isinstance(fb, bk.FakeBackend)


def test_make_backend_cloud_is_default_and_lazy():
    # Constructing CloudClaude must NOT import anthropic (only .complete does),
    # so make_backend("cloud") succeeds even without the package installed.
    b = bk.make_backend("cloud")
    assert isinstance(b, bk.CloudClaude)


def test_make_backend_unknown_raises():
    with pytest.raises(ValueError):
        bk.make_backend("nope")
