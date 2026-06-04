def test_constants_present():
    from vision import constants as C
    # ---- swing detection (hand-position trajectory) ----
    assert C.TRAJ_SMOOTH_WINDOW >= 1
    assert 0.0 < C.ADDRESS_REGION_RADIUS_FRAC < 1.0
    assert C.ADDRESS_REST_FRAMES >= 1
    assert C.MIN_RETURN_FRAMES >= 1
    assert 0.0 < C.MIN_SWING_AMPLITUDE_FRAC < 1.0
    assert C.MIN_SWING_FRAMES >= 1
    assert C.SWING_PAD_FRAMES >= 0
    # the old motion-energy knobs must be gone
    assert not hasattr(C, "MOTION_SMOOTH_WINDOW")
    assert not hasattr(C, "SWING_ENERGY_THRESH_FRAC")
    assert not hasattr(C, "MIN_STILL_FRAMES")
    assert not hasattr(C, "MIN_PEAK_FRAC")
    # segmentation block is untouched
    assert isinstance(C.PHASE_ORDER, tuple)
    assert C.PHASE_ORDER[0] == "address"
    assert C.PHASE_ORDER[-1] == "early_follow_through"
    assert len(C.PHASE_ORDER) == 8


def test_types_construct():
    from vision.types import FrameSample, SwingWindow, SwingResult
    fs = FrameSample(index=0, time_s=0.0,
                     view_crops={"down_line": None, "face_on": None})
    assert fs.index == 0 and "face_on" in fs.view_crops
    w = SwingWindow(start_index=10, end_index=120, peak_index=70)
    assert w.length() == 111
    r = SwingResult(swing_id=1, moments=[], frame_range=(10, 120),
                    view_layout="side_by_side_LR")
    assert r.swing_id == 1 and r.frame_range == (10, 120)
