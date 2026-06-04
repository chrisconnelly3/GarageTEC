"""Filter the GolfDB annotation table to a tour-pro swing manifest.

Input: golfDB.pkl (from the cloned wmcnally/golfdb repo; NOT vendored here -
it is CC BY-NC). Output: a list of swing manifest entries (plain dicts), one
per usable pro swing, carrying everything the extractor needs:
    id, youtube_id, player, sex, club, view, slow, events, bbox

Decisions (see the Phase-4 handoff doc for rationale):
  * Drop view == 'other' (only face-on / down-the-line have a defined camera
    geometry for our metrics).
  * Drop a hand-curated list of celebrity NON-pros (athletes/musicians who
    appear in GolfDB celebrity-swing clips). Everyone else in GolfDB is a real
    tour professional.
  * Keep both slow-mo and full-speed, but tag `slow` so the extractor / sampler
    can prefer slow == 0 (cleaner, less motion-blur, native frame cadence).

This module has NO heavy deps beyond pandas (only used to read the pickle).
"""
from typing import Dict, List, Optional

# GolfDB view strings -> our internal view names used by the metrics pipeline.
VIEW_MAP = {"face-on": "face_on", "down-the-line": "down_line"}

# Celebrity non-pros present in GolfDB (verified against the player roster).
# NFL QBs, MLB pitchers, musicians -- not tour professionals.
CELEBRITY_NON_PROS = {
    "BEN ROETHLISBERGER",   # NFL quarterback
    "BRANFORD MARSALIS",    # jazz musician
    "ROGER CLEMENS",        # MLB pitcher
    "TIM TEBOW",            # NFL quarterback
    "TOBY KEITH",           # country musician
}

# The 10-value GolfDB `events` array is [start_trim, e0..e7, end_trim]; the 8
# swing events live at events[1:-1]. Within those 8 (0-indexed): 0=Address,
# 1=Toe-up, 2=Mid-backswing, 3=Top, 4=Mid-downswing, 5=Impact,
# 6=Mid-follow-through, 7=Finish. So the absolute source-video frame for a
# named phase is events[1 + EVENT_OFFSET[phase]].
EVENT_OFFSET = {"address": 0, "top": 3, "impact": 5}


def phase_frame(events, phase: str) -> int:
    """Absolute source-video frame index for a named phase, from a GolfDB
    10-value events array."""
    return int(events[1 + EVENT_OFFSET[phase]])


def load_table(pkl_path: str):
    """Read golfDB.pkl into a pandas DataFrame."""
    import pandas as pd
    return pd.read_pickle(pkl_path)


def build_manifest(pkl_path: str,
                   exclude_players: Optional[set] = None) -> List[Dict]:
    """Return the list of usable tour-pro swing entries from golfDB.pkl."""
    exclude = CELEBRITY_NON_PROS if exclude_players is None else exclude_players
    df = load_table(pkl_path)
    out: List[Dict] = []
    for _, r in df.iterrows():
        view = r["view"]
        if view not in VIEW_MAP:
            continue  # drops 'other'
        player = str(r["player"]).strip()
        if player.upper() in exclude:
            continue
        out.append({
            "id": int(r["id"]),
            "youtube_id": str(r["youtube_id"]),
            "player": player,
            "sex": str(r["sex"]),
            "club": str(r["club"]),
            "view": view,                 # 'face-on' | 'down-the-line'
            "our_view": VIEW_MAP[view],   # 'face_on' | 'down_line'
            "slow": int(r["slow"]),
            "events": [int(x) for x in r["events"]],
            "bbox": [float(x) for x in r["bbox"]],
        })
    return out


def summarize(manifest: List[Dict]) -> Dict:
    """Counts for sanity-checking a manifest."""
    from collections import Counter
    by_view = Counter(m["view"] for m in manifest)
    by_view_slow = Counter((m["view"], m["slow"]) for m in manifest)
    players = {m["player"] for m in manifest}
    return {
        "n_swings": len(manifest),
        "n_players": len(players),
        "n_youtube": len({m["youtube_id"] for m in manifest}),
        "by_view": dict(by_view),
        "face_on_full_speed": by_view_slow.get(("face-on", 0), 0),
        "face_on_slowmo": by_view_slow.get(("face-on", 1), 0),
        "dtl_full_speed": by_view_slow.get(("down-the-line", 0), 0),
        "dtl_slowmo": by_view_slow.get(("down-the-line", 1), 0),
    }
