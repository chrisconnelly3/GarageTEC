from vision.run import build_arg_parser, resolve_player_and_session
from store import repo


def test_arg_parser_defaults_and_required():
    parser = build_arg_parser()
    args = parser.parse_args(["--video", "golf swing.MOV", "--player", "Chris"])
    assert args.video == "golf swing.MOV"
    assert args.player == "Chris"
    assert args.split == 0.5
    assert args.session is None
    assert args.render is False
    assert args.single_swing is False
    assert args.height == 72.0


def test_resolve_player_creates_and_reuses(db):
    pid1, sid1 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=None)
    assert pid1 is not None and sid1 is not None
    # second call reuses the same open session + player
    pid2, sid2 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=None)
    assert pid2 == pid1 and sid2 == sid1


def test_resolve_player_honors_explicit_session(db):
    pid = repo.get_or_create_player(db, "Chris", 72.0, "R").id
    sid = repo.create_session(db, pid).id
    pid2, sid2 = resolve_player_and_session(
        db, player="Chris", height_in=72.0, handedness="R", session_id=sid)
    assert pid2 == pid and sid2 == sid
