"""Pure dataclass -> JSON-safe dict builders for the Screen API."""
import json


def player_dict(p):
    return {"id": p.id, "name": p.name, "height_in": p.height_in,
            "handedness": p.handedness, "created_at": p.created_at}


def session_dict(s):
    return {"id": s.id, "player_id": s.player_id, "started_at": s.started_at,
            "ended_at": s.ended_at, "location": s.location, "notes": s.notes}


def swing_dict(sw):
    return {"id": sw.id, "session_id": sw.session_id, "player_id": sw.player_id,
            "created_at": sw.created_at, "source_video_path": sw.source_video_path,
            "view_layout": sw.view_layout, "fps": sw.fps, "width": sw.width,
            "height": sw.height, "club": sw.club, "notes": sw.notes,
            "shot_id": sw.shot_id}


def shot_dict(sh):
    if sh is None:
        return None
    return {"id": sh.id, "swing_id": sh.swing_id, "player_id": sh.player_id,
            "session_id": sh.session_id, "captured_at": sh.captured_at,
            "device_id": sh.device_id, "shot_number": sh.shot_number,
            "ball_speed": sh.ball_speed, "total_spin": sh.total_spin,
            "spin_axis": sh.spin_axis, "hla": sh.hla, "vla": sh.vla,
            "carry": sh.carry, "club_speed": sh.club_speed,
            "attack_angle": sh.attack_angle, "club_path": sh.club_path,
            "face_to_target": sh.face_to_target}


def moment_dict(m):
    return {"id": m.id, "swing_id": m.swing_id, "kind": m.kind, "view": m.view,
            "frame_index": m.frame_index, "time_s": m.time_s}


def metric_dict(m):
    return {"id": m.id, "swing_id": m.swing_id, "name": m.name,
            "context": m.context, "value": m.value, "unit": m.unit,
            "method": m.method, "created_at": m.created_at}


def media_dict(md):
    meta = json.loads(md.meta_json) if md.meta_json else None
    return {"id": md.id, "swing_id": md.swing_id, "kind": md.kind,
            "path": md.path, "meta": meta}


def coaching_dict(c):
    content = json.loads(c.content_json) if c.content_json else None
    return {"id": c.id, "swing_id": c.swing_id, "session_id": c.session_id,
            "kind": c.kind, "content": content, "model": c.model,
            "created_at": c.created_at}
