"""Assemble the structured grounding context for a swing or session.

Every number here comes from the store or the norms dataset; nothing is
invented. The result is a plain JSON-serializable dict consumed by prompt.py.
"""
import statistics

from store import repo
from coach import norms as norms_mod


def _player_dict(player):
    if player is None:
        return None
    return {"id": player.id, "name": player.name,
            "height_in": player.height_in, "handedness": player.handedness}


def _shot_dict(shot):
    if shot is None:
        return None
    return {
        "id": shot.id, "ball_speed": shot.ball_speed, "total_spin": shot.total_spin,
        "spin_axis": shot.spin_axis, "hla": shot.hla, "vla": shot.vla,
        "carry": shot.carry, "club_speed": shot.club_speed,
        "attack_angle": shot.attack_angle, "club_path": shot.club_path,
        "face_to_target": shot.face_to_target,
    }


def _metric_context(conn, player_id, metric, norms_data, exclude_swing_id):
    name = metric.name
    ctx_label = metric.context or "overall"
    hist = repo.swing_history(conn, player_id, name, context=ctx_label)
    prior = [v for (sid, _ts, v) in hist
             if sid != exclude_swing_id and v is not None]
    baseline = statistics.median(prior) if prior else None
    trend = None
    if len(prior) >= 2:
        trend = "up" if prior[-1] > prior[0] else (
            "down" if prior[-1] < prior[0] else "flat")
    vs_baseline = (metric.value - baseline
                   if baseline is not None and metric.value is not None else None)
    return {
        "name": name,
        "context": metric.context,
        "value": metric.value,
        "unit": metric.unit,
        "method": metric.method,
        "baseline": baseline,
        "history_n": len(prior),
        "trend": trend,
        "vs_baseline_delta": vs_baseline,
        "norms": norms_mod.compare(name, metric.value, norms=norms_data),
    }


def build_swing_context(conn, swing_id, norms_data=None):
    norms_data = norms_mod.load_norms() if norms_data is None else norms_data
    swing = repo.get_swing(conn, swing_id)
    if swing is None:
        raise ValueError(f"no swing with id {swing_id}")
    player = repo.get_player(conn, swing.player_id)
    shot = repo.get_shot(conn, swing.shot_id) if swing.shot_id else None
    metrics = repo.get_metrics(conn, swing_id)
    return {
        "kind": "swing",
        "swing_id": swing_id,
        "session_id": swing.session_id,
        "club": swing.club,
        "player": _player_dict(player),
        "shot": _shot_dict(shot),
        "metrics": [
            _metric_context(conn, swing.player_id, m, norms_data, swing_id)
            for m in metrics
        ],
    }


def build_session_context(conn, session_id, norms_data=None):
    norms_data = norms_mod.load_norms() if norms_data is None else norms_data
    swings = repo.list_swings(conn, session_id=session_id)
    swing_ctxs = [build_swing_context(conn, sw.id, norms_data=norms_data)
                  for sw in swings]
    player = repo.get_player(conn, swings[0].player_id) if swings else None
    return {
        "kind": "session",
        "session_id": session_id,
        "player": _player_dict(player),
        "swing_count": len(swing_ctxs),
        "swings": swing_ctxs,
    }
