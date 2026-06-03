from store import repo
from store.models import Shot
from sync import run as sync_run


def _seed_linkable(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    sw = repo.add_swing(db, sid, pid, "v.MOV")
    sh = repo.save_shot(db, Shot(captured_at="2026-06-03T00:00:01+00:00",
                                 player_id=pid, session_id=sid))
    return pid, sid, sw, sh


def test_main_session_reconciles(db, capsys):
    pid, sid, sw, sh = _seed_linkable(db)
    code = sync_run.main(["--session", str(sid), "--threshold", "0.5"], conn=db)
    assert code == 0
    assert repo.get_swing(db, sw.id).shot_id == sh.id
    out = capsys.readouterr().out
    assert "linked" in out.lower()


def test_main_all_reconciles(db):
    pid, sid, sw, sh = _seed_linkable(db)
    code = sync_run.main(["--all", "--threshold", "0.5"], conn=db)
    assert code == 0
    assert repo.get_swing(db, sw.id).shot_id == sh.id


def test_main_requires_a_mode(db):
    code = sync_run.main([], conn=db)
    assert code == 2  # argparse-style usage error
