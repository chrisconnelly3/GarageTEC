from web.backend import deps


def test_calibration_singletons_and_reset():
    bus = deps.calibration_bus()
    assert deps.calibration_bus() is bus               # singleton
    sup = deps.get_calibration_supervisor()
    assert deps.get_calibration_supervisor() is sup
    deps.reset_calibration_singletons()
    assert deps.calibration_bus() is not bus
