"""Tests for the GolfDB pro-reference pipeline (manifest / extract / aggregate).

No network or real video: manifest is tested against a synthetic pickled table,
extract against synthetic Landmark poses with known geometry, aggregate against
synthetic per-swing records.
"""
import json

import pytest

from store.models import Landmark
from coach.norms.pro_reference import manifest as M
from coach.norms.pro_reference import extract as E
from coach.norms.pro_reference import aggregate as A
from coach.norms.pro_reference import build_golftec_reference as G


# ---------------------------------------------------------------- manifest ----

def _events(address, top, impact):
    """A 10-value GolfDB events array placing the three named phases; other
    event slots filled with monotonic dummy frames."""
    return [address - 5, address, address + 2, address + 4, top,
            top + 3, impact, impact + 4, impact + 8, impact + 20]


def test_phase_frame_offsets():
    ev = _events(100, 140, 160)
    assert M.phase_frame(ev, "address") == 100
    assert M.phase_frame(ev, "top") == 140
    assert M.phase_frame(ev, "impact") == 160


def _tiny_table(tmp_path):
    import pandas as pd
    rows = [
        # real pro, face-on, full speed
        dict(id=1, youtube_id="aaa", player="RORY MCILROY", sex="m",
             club="driver", view="face-on", slow=0,
             events=_events(10, 40, 60), bbox=[0.1, 0.0, 0.5, 1.0]),
        # real pro, DTL, slow-mo
        dict(id=2, youtube_id="bbb", player="LYDIA KO", sex="f",
             club="iron", view="down-the-line", slow=1,
             events=_events(10, 40, 60), bbox=[0.1, 0.0, 0.5, 1.0]),
        # 'other' view -> dropped
        dict(id=3, youtube_id="ccc", player="TIGER WOODS", sex="m",
             club="driver", view="other", slow=0,
             events=_events(10, 40, 60), bbox=[0.1, 0.0, 0.5, 1.0]),
        # celebrity non-pro -> dropped
        dict(id=4, youtube_id="ddd", player="TIM TEBOW", sex="m",
             club="driver", view="face-on", slow=0,
             events=_events(10, 40, 60), bbox=[0.1, 0.0, 0.5, 1.0]),
    ]
    df = pd.DataFrame(rows)
    p = tmp_path / "tiny.pkl"
    df.to_pickle(str(p))
    return str(p)


def test_build_manifest_filters_other_and_celebrities(tmp_path):
    man = M.build_manifest(_tiny_table(tmp_path))
    ids = {m["id"] for m in man}
    assert ids == {1, 2}                      # 'other' + Tebow dropped
    by_id = {m["id"]: m for m in man}
    assert by_id[1]["our_view"] == "face_on"
    assert by_id[2]["our_view"] == "down_line"


def test_summarize_counts(tmp_path):
    man = M.build_manifest(_tiny_table(tmp_path))
    s = M.summarize(man)
    assert s["n_swings"] == 2
    assert s["n_players"] == 2
    assert s["by_view"] == {"face-on": 1, "down-the-line": 1}


# ----------------------------------------------------------------- extract ----

def _lm(name, x, y, vis=0.99):
    return Landmark(name=name, x=x, y=y, z=0.0, visibility=vis)


def _faceon_pose(sh_l, sh_r, hip_l, hip_r, nose=(50, 10)):
    return [
        _lm("left_shoulder", *sh_l), _lm("right_shoulder", *sh_r),
        _lm("left_hip", *hip_l), _lm("right_hip", *hip_r),
        _lm("nose", *nose),
    ]


def test_angle_metrics_faceon_tilt_known_geometry():
    # left_shoulder (0,0), right_shoulder (10,10): image-y down, so right is
    # LOWER -> line_angle_vs_horizontal negates dy -> -45 deg.
    pose = _faceon_pose((0, 0), (10, 10), (0, 50), (10, 50))
    m = E._angle_metrics({"address": pose}, "face_on")
    assert abs(m["shoulder_tilt_deg@address"] - (-45.0)) < 1e-6
    assert abs(m["hip_tilt_deg@address"] - 0.0) < 1e-6   # hips level


def test_angle_metrics_downline_spine_from_vertical():
    # shoulders centered at x=10, hips centered at x=0, vertical drop 50:
    # lean = atan2(|10-0|, 50) ~ 11.3 deg from vertical.
    pose = [
        _lm("left_shoulder", 8, 0), _lm("right_shoulder", 12, 0),
        _lm("left_hip", -2, 50), _lm("right_hip", 2, 50),
    ]
    m = E._angle_metrics({"top": pose}, "down_line")
    import math
    assert abs(m["spine_angle_deg@top"] - math.degrees(math.atan2(10, 50))) < 1e-6


def test_sway_metrics_scale_free_fraction_and_sign():
    # address: shoulder width 100 px, hip center x=50. impact: hip center x=70
    # -> net +20 -> sign +1. top hip center x=40 -> -10 px -> -0.10 of width.
    addr = _faceon_pose((0, 0), (100, 0), (40, 50), (60, 50))   # hip cx=50, sw=100
    top = _faceon_pose((0, 0), (100, 0), (30, 50), (50, 50))    # hip cx=40
    imp = _faceon_pose((0, 0), (100, 0), (60, 50), (80, 50))    # hip cx=70
    m = E._sway_metrics({"address": addr, "top": top, "impact": imp})
    assert abs(m["hip_sway_sw@top"] - (-0.10)) < 1e-6
    assert abs(m["hip_sway_sw@impact"] - (0.20)) < 1e-6


def test_detect_view_from_geometry():
    # face-on: wide shoulders relative to torso height -> ratio ~0.5
    faceon = _faceon_pose((0, 0), (50, 0), (10, 100), (40, 100))  # sw=50, torso=100
    assert E.detect_view(faceon) == "face_on"
    # down-the-line: shoulders foreshortened (narrow) -> small ratio
    dtl = _faceon_pose((20, 0), (26, 0), (20, 100), (26, 100))    # sw=6, torso=100
    assert E.detect_view(dtl) == "down_line"
    assert E.detect_view(None) is None


def test_shoulder_width_and_vis_guards():
    pose = _faceon_pose((0, 0), (10, 0), (0, 50), (10, 50))
    assert E._shoulder_width_px(pose) == 10.0
    assert E._mean_vis(pose) > 0.9
    # zero width -> None (avoids divide-by-zero downstream)
    degenerate = _faceon_pose((5, 0), (5, 0), (0, 50), (10, 50))
    assert E._shoulder_width_px(degenerate) is None


# --------------------------------------------------------------- aggregate ----

def test_acute_from_horizontal_folds_orientation():
    # near +/-180 (orientation wrap) -> small acute magnitude
    assert abs(A.acute_from_horizontal(-168.61) - 11.39) < 1e-6
    assert abs(A.acute_from_horizontal(173.75) - 6.25) < 1e-6
    assert abs(A.acute_from_horizontal(-45.0) - 45.0) < 1e-6
    assert abs(A.acute_from_horizontal(0.0) - 0.0) < 1e-6
    assert abs(A.acute_from_horizontal(12.0) - 12.0) < 1e-6   # already small


def test_aggregate_folds_tilt_but_not_spine():
    # a raw shoulder_tilt of -170 should aggregate as ~10 (folded), not -170.
    recs = [{"id": i, "player": f"P{i}", "view": "face-on", "club": "driver",
             "slow": 0, "vis": 0.9,
             "metrics": {"shoulder_tilt_deg@impact": -170.0,
                         "spine_angle_deg@impact": 25.0}} for i in range(3)]
    ent = A.aggregate(recs)
    assert abs(ent["shoulder_tilt_deg"]["contexts"]["impact"]["median"] - 10.0) < 0.1
    # spine is a magnitude already -> untouched
    assert abs(ent["spine_angle_deg"]["contexts"]["impact"]["median"] - 25.0) < 0.1


def test_percentile_linear_interpolation():
    vals = sorted(float(i) for i in range(1, 101))
    assert abs(A._percentile(vals, 0.50) - 50.5) < 0.5
    assert abs(A._percentile(vals, 0.10) - 10.9) < 0.5


def test_winsorize_only_kicks_in_when_large():
    small = [1.0, 2.0, 1000.0]
    assert A._winsorize(small) == small         # n<40 untouched
    # One extreme value beyond p99 of a large bulk -> clipped down to ~p99.
    big = [float(i) for i in range(1, 200)] + [1e9]
    out = A._winsorize(big)
    assert max(out) < 1000.0                    # extreme clipped to ~p99 (~198)
    assert min(out) >= 1.0                       # bulk lower tail preserved
    assert len(out) == len(big)                  # winsorize clips, never drops


def _records():
    recs = []
    # 25 face-on swings (enough for "high" on angle metrics, MIN_N_HIGH=20)
    for i in range(25):
        recs.append({
            "id": i, "player": f"PRO{i%7}", "view": "face-on",
            "club": "driver", "slow": 0, "vis": 0.9,
            "metrics": {
                "shoulder_tilt_deg@address": 8.0 + (i % 5),
                "shoulder_tilt_deg@impact": 20.0 + (i % 5),
                "hip_sway_sw@impact": 0.1 + 0.01 * (i % 5),
            },
        })
    # a few DTL swings (n<20 -> spine should be "low")
    for j in range(5):
        recs.append({
            "id": 100 + j, "player": f"DTL{j}", "view": "down-the-line",
            "club": "iron", "slow": 1, "vis": 0.9,
            "metrics": {"spine_angle_deg@address": 18.0 + j},
        })
    return recs


def test_aggregate_tiers_and_contexts():
    entries = A.aggregate(_records())
    st = entries["shoulder_tilt_deg"]
    assert st["confidence"] == "high"           # n=25 >= MIN_N_HIGH
    assert st["tier"] == "pro_ideal"
    assert st["units"] == "deg"
    assert set(st["contexts"]) == {"address", "impact"}
    assert st["contexts"]["address"]["n"] == 25

    sway = entries["hip_sway_sw"]
    assert sway["confidence"] == "provisional"
    assert sway["units"] == "fraction_shoulder_width"

    spine = entries["spine_angle_deg"]
    assert spine["confidence"] == "low"         # only 5 DTL swings

    assert entries["_n_swings_by_view"] == {"face-on": 25, "down-the-line": 5}


# ---------------------------------------------------- golftec authoritative ---

def test_golftec_shoulder_tilt_authoritative_and_2d_flags():
    e = G.build_entries()
    st = e["shoulder_tilt_deg"]
    assert st["authoritative"] is True
    assert st["tier"] == "pro_ideal_golftec"
    # address is square -> 2D-comparable now; top/impact rotate -> need 3D
    assert st["contexts"]["address"]["two_d_comparable_now"] is True
    assert st["contexts"]["address"]["needs_3d"] is False
    assert st["contexts"]["top"]["two_d_comparable_now"] is False
    assert st["contexts"]["impact"]["needs_3d"] is True
    # GolfTEC values (SwingTRU/Tour Avg)
    assert st["value_by_phase"]["address"] == 10
    assert st["value_by_phase"]["impact"] == 39


def test_golftec_turn_metrics_are_3d_only():
    e = G.build_entries()
    for m in ("shoulder_turn_deg", "hip_turn_deg"):
        assert e[m]["needs_3d_all"] is True
        assert all(not c["two_d_comparable_now"]
                   for c in e[m]["contexts"].values())
    # the famous benchmark values survive
    assert e["shoulder_turn_deg"]["value_by_phase"]["top"] == 89
    assert e["hip_turn_deg"]["value_by_phase"]["impact"] == 36


def test_golftec_hip_sway_is_2d_measurable():
    e = G.build_entries()
    sway = e["hip_sway_in"]
    assert sway["units"] == "in"
    assert sway["contexts"]["top"]["value"] == 3.9      # use GolfTEC over GolfDB
    assert sway["contexts"]["impact"]["value"] == 1.6
    assert sway["contexts"]["impact"]["two_d_comparable_now"] is True


def test_golftec_golfdb_only_metrics_have_no_value():
    e = G.build_entries()
    for m in ("head_sway_in", "hand_depth_in", "early_extension_in"):
        assert e[m]["tier"] == "golfdb_only"
        assert e[m]["authoritative"] is False
        assert e[m]["confidence"] == "none"


def test_golftec_meta_states_precedence_and_2d_caveat():
    meta = G.build_meta()
    assert "GolfTEC is trusted OVER" in meta["precedence"]
    assert "two_d_comparable_now" in meta["critical_2d_vs_3d_caveat"]
    assert meta["tier"] == "pro_ideal_golftec"


def test_golftec_main_writes_deterministically(tmp_path):
    import re
    out = tmp_path / "golftec_reference.json"
    G.main(str(out)); first = out.read_text(encoding="utf-8")
    G.main(str(out)); second = out.read_text(encoding="utf-8")
    norm = lambda s: re.sub(r'"generated":\s*"[^"]*"', '"generated":"X"', s)
    assert norm(first) == norm(second)
    doc = json.loads(first)
    assert doc["shoulder_turn_deg"]["value_by_phase"]["top"] == 89


def test_aggregate_main_writes_and_loads(tmp_path):
    recs_path = tmp_path / "records.jsonl"
    with open(recs_path, "w", encoding="utf-8") as f:
        for r in _records():
            f.write(json.dumps(r) + "\n")
    out = tmp_path / "pro_reference.json"
    A.main(str(recs_path), str(out))
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert doc["_meta"]["tier"] == "pro_ideal"
    assert "GolfDB" in doc["_meta"]["attribution"]
    assert doc["shoulder_tilt_deg"]["confidence"] == "high"
    assert doc["_meta"]["n_records"] == 30
