"""Idempotent dev seed: a demo player with processed swings so every Screen
renders real data without a live R50. Run:

    & 'C:\\Users\\chris\\AppData\\Local\\Programs\\Python\\Python312\\python.exe' -m web.backend.seed_dev
"""
import json
import random

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Media, Coaching

PLAYER = {"name": "Alex M.", "height_in": 72.0, "handedness": "R"}
TARGET_SWINGS = 3          # swings in the open/live session
HISTORY_SWINGS = 8         # extra older swings for trend charts
CONTEXTS = ("address", "top", "impact")

# (name, unit, method, baseline_value_at_impact, per-swing jitter)
METRIC_SPEC = [
    ("shoulder_tilt_deg", "deg", "exact", 38.0, 3.0),
    ("hip_tilt_deg", "deg", "exact", 12.0, 2.0),
    ("shoulder_turn_deg", "deg", "exact", 95.0, 5.0),
    ("hip_turn_deg", "deg", "exact", 48.0, 4.0),
    ("spine_angle_deg", "foreshortening_2d;confidence=low", "foreshortening_2d", 42.0, 2.0),
    ("hand_depth_in", "in", "exact", 14.0, 1.5),
    ("early_extension_in", "in", "exact", 1.8, 0.6),
    ("hip_sway_in", "in", "ratio", 2.5, 0.8),
    ("head_sway_in", "in", "ratio", 1.1, 0.5),
]


def _coaching_content():
    return {
        "headline": "Good power, but sliding hips are causing inconsistency.",
        "findings": [
            {"metric": "hip_sway_in", "context": "impact", "value": 2.5,
             "unit": "in", "vs_baseline": "+0.4 in vs your recent average",
             "vs_ideal": "above the 0-2 in ideal range",
             "ball_effect": "tends to push starts right",
             "severity": "bad"},
            {"metric": "shoulder_turn_deg", "context": "top", "value": 95.0,
             "unit": "deg", "vs_baseline": "+5 deg vs baseline",
             "vs_ideal": "inside the 90-110 deg ideal range",
             "ball_effect": "added ~3 mph club speed", "severity": "good"},
        ],
        "drills": [
            {"name": "Chair Drill", "why": "Stops the lead hip sliding past the ball",
             "how": "Set a chair against your lead hip; turn into it without touching."},
            {"name": "Pause at Top", "why": "Improves transition sequencing",
             "how": "Swing to the top, hold one beat, then start down from the ground up."},
        ],
        "confidence_notes": ["spine_angle_deg is foreshortening-estimated (low confidence)."],
    }


def _add_processed_swing(conn, session_id, player_id, *, club, jitter, with_shot,
                         with_coaching):
    sw = repo.add_swing(conn, session_id, player_id, "swings/seed/source.mp4",
                        view_layout="face_on", fps=240.0, width=1920,
                        height=1080, club=club)
    repo.save_moments(conn, sw.id, [
        Moment(sw.id, "address", "face_on", 0, 0.0),
        Moment(sw.id, "top", "face_on", 80, 0.33),
        Moment(sw.id, "impact", "face_on", 120, 0.50),
    ])
    metrics = []
    for name, unit, method, base, spread in METRIC_SPEC:
        for ctx in CONTEXTS:
            # vary by context so address<top<impact reads sensibly for the table
            scale = {"address": 0.25, "top": 0.7, "impact": 1.0}[ctx]
            val = round(base * scale + jitter * spread, 1)
            metrics.append(Metric(sw.id, name, ctx, val, unit, method))
    repo.save_metrics(conn, sw.id, metrics)
    repo.save_media(conn, Media(sw.id, "annotated_video", "swings/seed/annotated.mp4"))
    if with_shot:
        shot = repo.save_shot(conn, Shot(
            captured_at=dbmod.now_iso(), player_id=player_id, session_id=session_id,
            ball_speed=round(160 + jitter * 6, 1), total_spin=2450, spin_axis=-1.2,
            hla=0.8, vla=round(12.0 + jitter, 1), carry=round(280 + jitter * 8, 1),
            club_speed=round(110 + jitter * 3, 1), attack_angle=2.4, club_path=2.1,
            face_to_target=1.5))
        repo.link_shot_to_swing(conn, shot.id, sw.id)
    if with_coaching:
        repo.save_coaching(conn, Coaching(
            swing_id=sw.id, session_id=None, kind="swing",
            content_json=json.dumps(_coaching_content()), model="claude-seed"))
    return sw


def seed(conn):
    player = repo.get_or_create_player(conn, **PLAYER)

    # ---- history session (older, closed) for trend charts ----------------
    if not any(s.location == "seed-history"
               for s in repo.list_sessions(conn, player_id=player.id)):
        hist = repo.create_session(conn, player.id, location="seed-history")
        for i in range(HISTORY_SWINGS):
            # decreasing hip_sway over time -> visible downward trend
            _add_processed_swing(conn, hist.id, player.id, club="Driver",
                                 jitter=(HISTORY_SWINGS - i) * 0.15,
                                 with_shot=True, with_coaching=(i == HISTORY_SWINGS - 1))
        repo.end_session(conn, hist.id)

    # ---- live/open session for the Live + Sync screens -------------------
    open_sess = repo.get_open_session(conn, player.id)
    if open_sess is None:
        open_sess = repo.create_session(conn, player.id, location="seed-bay")
    existing = repo.list_swings(conn, session_id=open_sess.id)
    for i in range(max(0, TARGET_SWINGS - len(existing))):
        _add_processed_swing(conn, open_sess.id, player.id, club="7i",
                             jitter=random.uniform(-0.5, 0.5),
                             with_shot=(i < TARGET_SWINGS - 1),  # leave 1 unmatched for Sync
                             with_coaching=True)

    print(f"Seeded player={player.id} open_session={open_sess.id} "
          f"swings={len(repo.list_swings(conn, session_id=open_sess.id))}")
    return player


def main():
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    try:
        seed(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
