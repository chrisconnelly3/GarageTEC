import pytest

from store import repo
from metrics.compute import compute_metrics
from metrics.tests.conftest import seed_swing


def _full_swing(db):
    # A swing with both views and address/top/impact so most metrics produce rows.
    addr_fo = {"left_shoulder": (450.0, 200.0), "right_shoulder": (550.0, 200.0),
               "left_hip": (470.0, 400.0), "right_hip": (530.0, 400.0),
               "nose": (500.0, 120.0)}
    top_fo = {"left_shoulder": (470.0, 210.0), "right_shoulder": (540.0, 190.0),
              "left_hip": (480.0, 400.0), "right_hip": (520.0, 400.0),
              "nose": (505.0, 122.0)}
    imp_fo = {"left_shoulder": (450.0, 240.0), "right_shoulder": (550.0, 160.0),
              "left_hip": (490.0, 400.0), "right_hip": (550.0, 400.0),
              "nose": (520.0, 120.0)}
    addr_dl = {"left_shoulder": (700.0, 300.0), "right_shoulder": (700.0, 300.0),
               "left_hip": (700.0, 500.0), "right_hip": (700.0, 500.0),
               "left_wrist": (740.0, 450.0), "right_wrist": (740.0, 450.0)}
    imp_dl = {"left_shoulder": (720.0, 290.0), "right_shoulder": (720.0, 290.0),
              "left_hip": (730.0, 470.0), "right_hip": (730.0, 470.0),
              "left_wrist": (760.0, 450.0), "right_wrist": (760.0, 450.0)}
    return seed_swing(
        db, height_in=72.0,
        face_on_frames=[(0, addr_fo), (20, top_fo), (40, imp_fo)],
        down_line_frames=[(0, addr_dl), (20, addr_dl), (40, imp_dl)],
        moments=[("address", "face_on", 0), ("top", "face_on", 20),
                 ("impact", "face_on", 40),
                 ("address", "down_line", 0), ("top", "down_line", 20),
                 ("impact", "down_line", 40)],
    )


def test_compute_writes_all_metric_families(db):
    sw = _full_swing(db)
    written = compute_metrics(db, sw)
    names = {m.name for m in written}
    assert {"shoulder_tilt_deg", "hip_tilt_deg", "head_sway_in", "hip_sway_in",
            "spine_angle_deg", "early_extension_in", "hand_depth_in",
            "shoulder_turn_deg", "hip_turn_deg"} <= names
    # persisted to the store
    stored = repo.get_metrics(db, sw)
    assert len(stored) == len(written)


def test_compute_is_idempotent_no_duplicates(db):
    sw = _full_swing(db)
    first = compute_metrics(db, sw)
    n1 = len(repo.get_metrics(db, sw))
    second = compute_metrics(db, sw)
    n2 = len(repo.get_metrics(db, sw))
    assert n1 == n2  # replaced, not appended
    assert len(first) == len(second)


def test_compute_low_confidence_tag_on_rotations(db):
    sw = _full_swing(db)
    compute_metrics(db, sw)
    rot = [m for m in repo.get_metrics(db, sw)
           if m.name in ("shoulder_turn_deg", "hip_turn_deg")]
    assert rot  # present
    assert all(m.method == "foreshortening_2d;confidence=low" for m in rot)


def test_compute_reliable_methods(db):
    sw = _full_swing(db)
    compute_metrics(db, sw)
    by_name = {}
    for m in repo.get_metrics(db, sw):
        by_name.setdefault(m.name, m)
    assert by_name["shoulder_tilt_deg"].method == "exact"
    assert by_name["spine_angle_deg"].method == "exact"
    assert by_name["hip_sway_in"].method == "shoulder_ratio_0.24"
    assert by_name["hand_depth_in"].method == "shoulder_ratio_0.24"
