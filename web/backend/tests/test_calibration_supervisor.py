import numpy as np
from store import db as dbmod, repo
from web.backend.calibration import CalibrationEventBus, CalibrationSupervisor
from vision.threed.checkerboard import BoardDetection


def _conn():
    c = dbmod.connect(":memory:"); dbmod.init_db(conn=c); return c


def _det(found, cx=100, cy=100):
    n = 54
    corners = np.zeros((n, 1, 2), np.float32)
    return BoardDetection(found_both=found, fo_corners=corners, dl_corners=corners,
                          fo_center=(cx, cy), dl_center=(cx, cy))


def test_process_frame_accumulates_new_coverage_only(monkeypatch):
    conn = _conn(); bus = CalibrationEventBus()
    sup = CalibrationSupervisor(conn=conn, bus=bus)
    # configure() sets params WITHOUT spawning the capture thread, so we drive
    # process_frame deterministically (no background thread racing the count).
    sup.configure(device_index=0, cols=9, rows=6, square_mm=25.0)
    # same position twice -> 1 pose; new cell -> 2
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 100, 100))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == 1
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 600, 400))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == 2


def test_run_calibrates_and_persists(monkeypatch):
    conn = _conn(); bus = CalibrationEventBus()
    sup = CalibrationSupervisor(conn=conn, bus=bus)
    sup.configure(device_index=0, cols=9, rows=6, square_mm=25.0)
    # stub the engine so the test is deterministic
    from vision.threed.checkerboard import CalibrationResult
    monkeypatch.setattr("web.backend.calibration.stereo_calibrate",
                        lambda *a, **k: CalibrationResult(
                            calib={"image_width": 640}, reprojection_error=0.4, n_poses=10))
    # seed 10 accumulated poses (each a new coverage cell in 4x3 grid over 320x480 half)
    _positions = [(40,60),(120,60),(200,60),(280,60),(40,180),(120,180),
                  (200,180),(280,180),(40,380),(120,380)]
    for cx, cy in _positions:
        monkeypatch.setattr("web.backend.calibration.detect_board",
                            lambda *a, _cx=cx, _cy=cy, **k: _det(True, _cx, _cy))
        sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    result = sup.run()
    assert result["ok"] is True and result["n_poses"] >= 8
    assert repo.get_active_calibration(conn) is not None
