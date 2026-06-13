"""Rich DEMO seed: a 'fully lit up' dataset for UX/UI review.

Unlike `seed_dev` (a minimal dev fixture), this fills EVERY screen with
realistic data so you can feel the product as if the bay were live:
  - Body cards light up green/yellow/red at top + impact (metrics are written
    with a `triangulated_3d` method, so the 2D/3D gate treats them as
    calibrated; no actual cameras needed).
  - Head-sway is written with the correct NEGATIVE (trail-side) sign at the top,
    so the directional comparison reads GREEN for a good load.
  - Ball cards + per-club Ball-history populate (Driver / 7 Iron / PW / 5 Iron).
  - History trends span ~3 weeks of backdated sessions (real date/time axis).
  - Connect shows an active calibration in history.
  - The real `smooth_swing.mov` is wired as each swing's video, with phase
    moments at real timestamps so playback + scrubbing + the phase jumper work.

Run (resets the dev DB first is recommended):
    python -m web.backend.seed_demo
"""
import json
import random
import shutil
from datetime import datetime, timedelta, timezone

from store import db as dbmod
from store import repo
from store.models import Shot, Moment, Metric, Coaching, Media
from coach.ball_reference import TRACKMAN

# Deterministic so re-runs look the same.
random.seed(7)

REPO_VIDEO = "smooth_swing.mov"                 # at repo root
MEDIA_REL = "swings/smooth_swing.mov"            # served at /media/swings/smooth_swing.mov
REPO_POSE = "smooth_swing.pose.json"            # per-frame skeleton at repo root
POSE_REL = "swings/smooth_swing.pose.json"       # served at /media/swings/smooth_swing.pose.json

# Per-(metric, phase) demo plan: (name, context, base_value, method, unit).
# Values are chosen relative to the tour targets to yield a realistic mix of
# zones (mostly green, a couple yellow). 3D method => the card is benchmarked
# (lit) rather than "NEEDS 3D". Head-sway @ top is negative on purpose.
_3D = "triangulated_3d;confidence=medium"
DEMO_PLAN = [
    # address (2D, comparable now)
    ("shoulder_tilt_deg", "address", 11.0, "exact", "deg"),
    ("hip_tilt_deg",      "address", 2.0,  "exact", "deg"),
    ("spine_angle_deg",   "address", 35.0, "exact", "deg"),
    # top
    ("shoulder_tilt_deg", "top", 37.0, _3D, "deg"),     # tour 36 -> green
    ("hip_tilt_deg",      "top", 12.0, _3D, "deg"),     # tour 11 -> green
    ("spine_angle_deg",   "top", 3.0,  _3D, "deg"),     # tour 2  -> green
    ("shoulder_turn_deg", "top", 92.0, _3D, "deg"),     # tour 89 -> green
    ("hip_turn_deg",      "top", 44.0, _3D, "deg"),     # tour 48 -> green
    ("x_factor_deg",      "top", 46.0, _3D, "deg"),     # tour 43 -> green
    ("hip_sway_in",       "top", 4.1,  "ratio", "in"),  # tour 3.9 (lower) -> green
    ("head_sway_in",      "top", -4.0, "ratio", "in"),  # tour -4.5 (match) -> green
    # impact
    ("shoulder_tilt_deg", "impact", 40.0, _3D, "deg"),  # tour 39 -> green
    ("hip_tilt_deg",      "impact", 15.0, _3D, "deg"),  # tour 14 -> green
    ("spine_angle_deg",   "impact", 21.0, _3D, "deg"),  # tour 17 -> yellow
    ("shoulder_turn_deg", "impact", 46.0, _3D, "deg"),  # tour 48 -> green
    ("hip_turn_deg",      "impact", 42.0, _3D, "deg"),  # tour 36 -> yellow
    ("hip_sway_in",       "impact", 1.8,  "ratio", "in"),  # tour 1.6 -> green
    ("early_extension_in","impact", 0.6,  "exact", "in"),  # target 0 -> green
    ("hand_depth_in",     "impact", 14.0, "exact", "in"),  # raw (no tour ref)
    # downswing
    ("x_factor_stretch_deg", "downswing", 5.5, _3D, "deg"),  # tour 5
]


def _now():
    return datetime.now(timezone.utc)


def _video_geometry(path):
    """(duration_s, fps, frame_count) of the video, with safe fallbacks."""
    try:
        import cv2
        cap = cv2.VideoCapture(path)
        fps = cap.get(cv2.CAP_PROP_FPS) or 0
        n = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        cap.release()
        if fps > 0 and n > 0:
            return n / fps, fps, int(n)
    except Exception:
        pass
    return 2.0, 30.0, 60


def _coaching(headline, findings, summary):
    return json.dumps({
        "headline": headline,
        "summary": summary,
        "findings": findings,
        "drills": [
            {"name": "Chair Drill", "why": "Stops the lead hip sliding past the ball",
             "how": "Set a chair against your lead hip; turn into it without touching."},
            {"name": "Pause at Top", "why": "Improves transition sequencing",
             "how": "Swing to the top, hold one beat, then start down from the ground up."},
        ],
        "confidence_notes": ["spine_angle is foreshortening-estimated at address."],
    })


def _metrics_for(swing_id, jitter):
    out = []
    for name, ctx, base, method, unit in DEMO_PLAN:
        spread = 1.5 if unit == "deg" else 0.18
        val = round(base + jitter * spread, 1)
        out.append(Metric(swing_id, name, ctx, val, unit, method))
    return out


def _shot_for(club, player_id, session_id, captured_at, jitter):
    """A realistic R50 shot near the TrackMan tour average for `club`."""
    t = TRACKMAN[club]
    spin_axis = round(random.uniform(-2.5, 2.5), 1)
    raw = json.dumps({"BallData": {"Speed": t["ball_speed"], "SpinAxis": spin_axis,
                                    "TotalSpin": t["spin"], "VLA": t["launch"],
                                    "CarryDistance": t["carry"]},
                      "ClubData": {"Speed": t["club_speed"],
                                   "AngleOfAttack": t["attack_angle"]}})
    # Believable "good amateur chasing tour" offsets so the stoplight actually
    # discriminates (not all-green): a touch slow, a little short, spin too high,
    # launch a hair high. Club speed + attack stay close (green).
    return Shot(
        captured_at=captured_at, player_id=player_id, session_id=session_id,
        ball_speed=round(t["ball_speed"] - 3.0 + jitter * 1.2, 1),   # ~3 slow -> yellow
        total_spin=int(t["spin"] + 480 + jitter * 120),             # spinny -> red
        spin_axis=spin_axis,
        hla=round(random.uniform(-1.5, 1.5), 1),
        vla=round(t["launch"] + 1.3 + jitter * 0.4, 1),             # a hair high -> yellow
        carry=round(t["carry"] - 6.0 + jitter * 2, 1),              # ~6 short -> yellow
        club_speed=round(t["club_speed"] - 1.0 + jitter * 0.8, 1),  # close -> green
        attack_angle=round(t["attack_angle"] + jitter * 0.4, 1),    # on tour -> green
        club_path=round(random.uniform(-2.0, 2.0), 1),
        face_to_target=round(random.uniform(-1.5, 1.5), 1),
        club=club, raw_json=raw)


def _add_swing(conn, *, session_id, player_id, club, created_at, moments,
               with_shot=True, with_coaching=True, with_video=True, jitter=0.0):
    sw = repo.add_swing(conn, session_id, player_id,
                        MEDIA_REL if with_video else "swings/seed/source.mp4",
                        view_layout="face_on", fps=240.0, width=1920, height=1080,
                        club=club)
    repo.save_moments(conn, sw.id, moments(sw.id))
    repo.save_metrics(conn, sw.id, _metrics_for(sw.id, jitter))
    if with_video:
        repo.save_media(conn, Media(sw.id, "annotated_video", MEDIA_REL))
        # Per-frame pose skeleton for the toggleable exoskeleton overlay.
        repo.save_media(conn, Media(sw.id, "pose_overlay", POSE_REL))
    if with_shot:
        shot = repo.save_shot(conn, _shot_for(club, player_id, session_id,
                                              created_at, jitter))
        repo.link_shot_to_swing(conn, shot.id, sw.id)
    if with_coaching:
        repo.save_coaching(conn, Coaching(
            swing_id=sw.id, session_id=None, kind="swing",
            content_json=_coaching(
                "Solid impact position; a touch of late extension to tidy up.",
                [{"metric": "hip_turn_deg", "context": "impact", "value": 42.0,
                  "unit": "deg", "vs_baseline": "+1 deg vs your recent average",
                  "vs_ideal": "a hair open vs the 36 deg tour mark",
                  "ball_effect": "starts the ball slightly left", "severity": "neutral"},
                 {"metric": "shoulder_tilt_deg", "context": "impact", "value": 40.0,
                  "unit": "deg", "vs_baseline": "matches your baseline",
                  "vs_ideal": "right on the 39 deg tour mark",
                  "ball_effect": "good low-point control", "severity": "good"}],
                "This is a quality strike. Your shoulder tilt of 40 deg at "
                "impact sits right on the 39 deg tour benchmark, so you're "
                "delivering the club on a clean descending arc and controlling "
                "your low point beautifully -- that's why the ball is coming off "
                "with tour-level speed. The one thing I'd tidy is the hip turn: "
                "at 42 deg you're a touch more open than the 36 deg mark and a "
                "hair past your own average, which is nudging the start line "
                "left. Settle that rotation down and you'll keep this compression "
                "while tightening up your start direction."),
            model="claude-demo"))
    # Backdate created_at so History spans real days/times.
    conn.execute("UPDATE swing SET created_at=? WHERE id=?", (created_at, sw.id))
    conn.commit()
    return sw


def _moments_factory(dur, fps):
    # Calibrated to smooth_swing.mov's actual swing window (the clip has lead-in
    # and follow-through padding, so address is not at t=0). Real captured swings
    # get detected moment times from the pipeline. We emit ALL eight swing
    # positions so the Live position stepper shows every one at its real time;
    # body metrics still only exist at address/top/impact.
    #
    # kind strings must map (via momentKindToLabel) to the stepper's PHASE_LABELS:
    # Address, Takeaway, Lead-arm, Top, Transition, Shaft par., Impact, Follow-thru.
    # Times verified frame-by-frame against smooth_swing.mov (lead-wrist height
    # trajectory + visual check). The clip is slow, so the swing window is wide.
    positions = [
        ("address",     1.95),
        ("takeaway",    2.75),
        ("lead-arm",    3.65),
        ("top",         4.57),
        ("transition",  4.85),
        ("shaft par.",  5.15),
        ("impact",      5.42),
        ("follow-thru", 5.85),
    ]

    def make(swing_id):
        out = []
        for kind, t in positions:
            ts = min(t, dur)
            out.append(Moment(swing_id, kind, "face_on", int(ts * fps), ts))
        return out
    return make


def _wipe(conn):
    """Clear all demo domain rows so each reseed is deterministic (the seed is a
    full reset, not an append). Schema/settings are preserved."""
    conn.execute("PRAGMA foreign_keys=OFF")
    for table in ("coaching", "media", "metric", "moment", "pose_3d_frame",
                  "pose_frame", "shot", "calibration", "swing", "session",
                  "player"):
        try:
            conn.execute(f"DELETE FROM {table}")
            conn.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
        except Exception:  # noqa: BLE001 - table/sequence may not exist
            pass
    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()


def seed(conn, media_root):
    _wipe(conn)
    # Copy the real swing video into the served media dir.
    dur, fps, _ = 2.0, 30.0, 0
    src = None
    import os
    if os.path.exists(REPO_VIDEO):
        dest = media_root / "swings" / "smooth_swing.mov"
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(REPO_VIDEO, dest)
        src = str(dest)
        dur, fps, _ = _video_geometry(src)
        print(f"video: {REPO_VIDEO} -> {dest} ({dur:.2f}s @ {fps:.0f}fps)")
        # Copy the per-frame pose skeleton next to it (drives the overlay).
        if os.path.exists(REPO_POSE):
            shutil.copyfile(REPO_POSE, media_root / "swings" / "smooth_swing.pose.json")
            print(f"pose:  {REPO_POSE} -> served at /media/{POSE_REL}")
        else:
            print(f"WARNING: {REPO_POSE} not found; overlay will be unavailable.")
    else:
        print(f"WARNING: {REPO_VIDEO} not found; swings will show the placeholder.")
    moments = _moments_factory(dur, fps)
    has_video = src is not None

    clubs_cycle = ["Driver", "7 Iron", "Driver", "PW", "7 Iron", "Driver", "5 Iron"]

    # ---- Alex M. (primary, right-handed): rich multi-session history --------
    alex = repo.get_or_create_player(conn, name="Alex M.", height_in=72.0, handedness="R")
    # 4 past sessions (history) + 1 open session (today, for Live/Sync).
    day_offsets = [21, 14, 7, 1]
    ci = 0
    for d in day_offsets:
        day = _now() - timedelta(days=d)
        sess = repo.create_session(conn, alex.id, location=f"Bay session -{d}d")
        conn.execute("UPDATE session SET started_at=? WHERE id=?",
                     (day.isoformat(), sess.id))
        n = random.randint(4, 6)
        for k in range(n):
            club = clubs_cycle[ci % len(clubs_cycle)]; ci += 1
            ts = (day + timedelta(minutes=4 * k)).isoformat()
            # gentle improvement over time: older sessions jitter higher
            j = (d / 7.0) + random.uniform(-0.6, 0.6)
            _add_swing(conn, session_id=sess.id, player_id=alex.id, club=club,
                       created_at=ts, moments=moments, jitter=round(j, 2),
                       with_video=has_video)
        repo.end_session(conn, sess.id)

    # Open (today) session. Matched swings are the most RECENT, so the latest
    # swing on Live is fully lit (body + ball + video + coaching). An unmatched
    # swing plus a nearby unmatched shot (~40s apart) sit OLDER in the session
    # so the Sync screen shows a proposal without stealing the Live latest.
    today = _now()
    open_sess = repo.create_session(conn, alex.id, location="Today's bay")
    # NOTE: the API's "latest" swing is the most-recently INSERTED (highest id),
    # not the newest created_at. So insert the Sync candidates FIRST (lower id),
    # then the matched swings oldest -> newest, so the last-inserted Alex swing
    # is the most recent AND fully matched (Live opens fully lit).
    u_swing_t = today - timedelta(minutes=40)
    _add_swing(conn, session_id=open_sess.id, player_id=alex.id, club="Driver",
               created_at=u_swing_t.isoformat(), moments=moments, with_shot=False,
               jitter=0.2, with_video=has_video)
    repo.save_shot(conn, _shot_for("Driver", alex.id, open_sess.id,
                                   (u_swing_t + timedelta(seconds=40)).isoformat(), 0.3))
    repo.save_shot(conn, _shot_for("7 Iron", alex.id, open_sess.id,
                                   (today - timedelta(minutes=52)).isoformat(), 0.2))
    for k in range(3, -1, -1):                        # inserts -21, -15, -9, -3 (last)
        club = clubs_cycle[ci % len(clubs_cycle)]; ci += 1
        ts = (today - timedelta(minutes=3 + 6 * k)).isoformat()
        _add_swing(conn, session_id=open_sess.id, player_id=alex.id, club=club,
                   created_at=ts, moments=moments,
                   jitter=round(random.uniform(-0.6, 0.6), 2), with_video=has_video)

    # ---- Jordan P. (left-handed): a couple sessions --------------------------
    jordan = repo.get_or_create_player(conn, name="Jordan P.", height_in=66.0, handedness="L")
    for d in (10, 3):
        day = _now() - timedelta(days=d)
        sess = repo.create_session(conn, jordan.id, location=f"Range -{d}d")
        conn.execute("UPDATE session SET started_at=? WHERE id=?",
                     (day.isoformat(), sess.id))
        for k in range(random.randint(3, 5)):
            club = clubs_cycle[ci % len(clubs_cycle)]; ci += 1
            ts = (day + timedelta(minutes=5 * k)).isoformat()
            _add_swing(conn, session_id=sess.id, player_id=jordan.id, club=club,
                       created_at=ts, moments=moments,
                       jitter=round(random.uniform(-0.5, 1.0), 2), with_video=has_video)
        repo.end_session(conn, sess.id)

    # ---- Sam R. (light data) -------------------------------------------------
    sam = repo.get_or_create_player(conn, name="Sam R.", height_in=70.0, handedness="R")
    day = _now() - timedelta(days=5)
    sess = repo.create_session(conn, sam.id, location="First lesson")
    conn.execute("UPDATE session SET started_at=? WHERE id=?", (day.isoformat(), sess.id))
    for k in range(3):
        ts = (day + timedelta(minutes=6 * k)).isoformat()
        _add_swing(conn, session_id=sess.id, player_id=sam.id, club="7 Iron",
                   created_at=ts, moments=moments,
                   jitter=round(random.uniform(0.5, 1.8), 2), with_video=has_video)
    repo.end_session(conn, sess.id)

    # ---- An active calibration so Connect shows history ----------------------
    repo.save_calibration(conn, device_index=0, cols=9, rows=6, square_mm=25.4,
                          n_poses=26, reprojection_error=0.42, calib_json="{}")
    conn.commit()

    # ---- Real PGA-coach output for Alex's latest matched swing ---------------
    # When ANTHROPIC_API_KEY is configured, generate genuine coaching for the
    # swing the Live screen opens on, so the demo shows the real agent (not the
    # mock). Best-effort: any failure (no key, API/validation error) is ignored
    # and the mock coaching stands in.
    import os
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            from coach import coach as _coach, backend as _backend
            be = _backend.make_backend("cloud")
            ss = repo.list_swing_summaries(conn, player_id=alex.id, limit=12)
            sid = next((s["id"] for s in ss if s.get("has_shot")), None)
            if sid is not None:
                _coach.coach_swing(conn, be, sid)
                print(f"real coaching generated for swing {sid}")
            # Session-level takeaways (what improved/slipped) for Alex's two most
            # recent completed sessions, so the Sessions cards show a real one.
            ended = [s for s in repo.list_sessions(conn, player_id=alex.id)
                     if s.ended_at]
            for s in ended[:2]:
                _coach.coach_session(conn, be, s.id)
                print(f"real session takeaway generated for session {s.id}")
        except Exception as e:   # noqa: BLE001 - demo convenience, never fatal
            print(f"real coaching skipped: {e}")

    n_players = len(repo.list_players(conn)) if hasattr(repo, "list_players") else 3
    print(f"Demo seeded: players~{n_players}, Alex open_session={open_sess.id}. "
          f"Live/Review/History/Sync/Connect are populated.")


def main():
    from web.backend.app import _load_dotenv  # picks up ANTHROPIC_API_KEY from .env
    _load_dotenv()
    conn = dbmod.connect()
    dbmod.init_db(conn=conn)
    from web.backend.deps import media_root
    try:
        seed(conn, media_root())
    finally:
        conn.close()


if __name__ == "__main__":
    main()
