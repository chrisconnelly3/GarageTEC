import numpy as np
from store import db as dbmod, repo
from web.backend.calibration import (
    CalibrationEventBus, CalibrationSupervisor, MIN_RUN_POSES, MAX_POSES)
from vision.threed.checkerboard import BoardDetection, CalibrationResult


def _conn():
    c = dbmod.connect(":memory:"); dbmod.init_db(conn=c); return c


def _det(found, cx=100, cy=100):
    corners = np.zeros((54, 1, 2), np.float32)
    return BoardDetection(found_both=found, fo_corners=corners, dl_corners=corners,
                          fo_center=(cx, cy), dl_center=(cx, cy))


def _sup():
    return CalibrationSupervisor(conn=_conn(), bus=CalibrationEventBus())


def test_process_frame_accepts_new_position_only(monkeypatch):
    sup = _sup()
    sup.configure(device_left=0, device_right=1, cols=9, rows=6, square_mm=25.0)
    # constant tilt so dedup is purely by position cell
    monkeypatch.setattr("web.backend.calibration.estimate_tilt_deg",
                        lambda *a, **k: 5.0)
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 100, 100))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))   # same cell+tilt -> 1
    assert sup.status()["good_poses"] == 1
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 600, 400))
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))   # new cell -> 2
    assert sup.status()["good_poses"] == 2


def test_varied_angle_accepts_same_cell_different_tilt(monkeypatch):
    # same board POSITION but different TILT buckets -> each accepted
    sup = _sup()
    sup.configure(device_left=0, device_right=1, cols=9, rows=6, square_mm=25.0)
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 100, 100))
    tilts = [2.0, 15.0, 28.0]            # buckets 0, 1, 2 (TILT_BUCKET_DEG=12)
    for t in tilts:
        monkeypatch.setattr("web.backend.calibration.estimate_tilt_deg",
                            lambda *a, _t=t, **k: _t)
        sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == 3
    assert sup.status()["tilt_buckets"] == 3


def test_caps_at_max_poses(monkeypatch):
    sup = _sup()
    sup.configure(device_left=0, device_right=1, cols=9, rows=6, square_mm=25.0)
    monkeypatch.setattr("web.backend.calibration.detect_board",
                        lambda *a, **k: _det(True, 100, 100))
    # feed many distinct (cell, tilt) combos across the 4x3 grid x 5 tilt
    # buckets (60 possible) -> accumulation should stop at MAX_POSES (30).
    for cx in (40, 120, 200, 300):          # 4 columns over the 320-wide half
        for cy in (80, 240, 400):           # 3 rows
            for tilt in (2.0, 15.0, 28.0, 40.0, 52.0):
                monkeypatch.setattr("web.backend.calibration.detect_board",
                                    lambda *a, _cx=cx, _cy=cy, **k: _det(True, _cx, _cy))
                monkeypatch.setattr("web.backend.calibration.estimate_tilt_deg",
                                    lambda *a, _t=tilt, **k: _t)
                sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert sup.status()["good_poses"] == MAX_POSES


def test_run_calibrates_and_persists(monkeypatch):
    conn = _conn(); sup = CalibrationSupervisor(conn=conn, bus=CalibrationEventBus())
    sup.configure(device_left=0, device_right=1, cols=9, rows=6, square_mm=25.0)
    monkeypatch.setattr("web.backend.calibration.stereo_calibrate",
                        lambda *a, **k: CalibrationResult(
                            calib={"image_width": 640}, reprojection_error=0.4,
                            n_poses=MIN_RUN_POSES))
    # seed >= MIN_RUN_POSES accumulated poses directly
    for _ in range(MIN_RUN_POSES):
        sup._obj.append(np.zeros((54, 3), np.float32))
        sup._fo.append(np.zeros((54, 1, 2), np.float32))
        sup._dl.append(np.zeros((54, 1, 2), np.float32))
    result = sup.run()
    assert result["ok"] is True and result["n_poses"] >= MIN_RUN_POSES
    assert repo.get_active_calibration(conn) is not None


def test_run_requires_min_poses():
    sup = _sup()
    sup.configure(device_left=0, device_right=1, cols=9, rows=6, square_mm=25.0)
    out = sup.run()
    assert out["ok"] is False and "15" in out["error"]   # MIN_RUN_POSES


def test_mono_mode_forwards_flag_and_uses_full_frame(monkeypatch):
    sup = _sup()
    sup.configure(device_left=0, cols=9, rows=6, square_mm=25.4, mono=True)
    seen = {}

    def fake_detect(composite, cols, rows, split=0.5, mono=False):
        seen["mono"] = mono
        return _det(True, 100, 100)

    monkeypatch.setattr("web.backend.calibration.detect_board", fake_detect)
    monkeypatch.setattr("web.backend.calibration.estimate_tilt_deg",
                        lambda *a, **k: 5.0)
    sup.process_frame(np.zeros((480, 640, 3), np.uint8))
    assert seen["mono"] is True
    assert sup.image_size == (640, 480)
    assert sup.status()["good_poses"] == 1
    out = sup.run()
    assert out["ok"] is False and out.get("mono") is True
