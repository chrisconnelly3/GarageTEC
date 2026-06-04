from web.backend import deps
from web.backend.capture import CaptureSupervisor, CaptureEventBus


def test_capture_bus_is_a_singleton():
    deps.reset_capture_singletons()
    assert deps.capture_bus() is deps.capture_bus()


def test_get_supervisor_is_a_singleton_and_uses_the_shared_bus():
    deps.reset_capture_singletons()
    sup = deps.get_supervisor()
    assert isinstance(sup, CaptureSupervisor)
    assert deps.get_supervisor() is sup
    assert sup.bus is deps.capture_bus()


def test_reset_clears_the_singletons():
    deps.reset_capture_singletons()
    first = deps.get_supervisor()
    deps.reset_capture_singletons()
    assert deps.get_supervisor() is not first
