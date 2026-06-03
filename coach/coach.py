"""Orchestrate grounded coaching: context -> backend -> validate -> store."""
import json

from store import repo
from store.models import Coaching
from coach import context as context_mod
from coach import prompt as prompt_mod


class CoachingValidationError(ValueError):
    """Raised when backend output fails schema/grounding validation.
    Nothing is persisted when this is raised."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__("coaching output failed validation: " + "; ".join(errors))


def _generate(conn, backend, context, *, kind, swing_id, session_id):
    user = prompt_mod.build_user(context)
    output = backend.complete(prompt_mod.SYSTEM, user, prompt_mod.OUTPUT_SCHEMA)
    ok, errors = prompt_mod.validate(output, context)
    if not ok:
        raise CoachingValidationError(errors)
    return repo.save_coaching(conn, Coaching(
        swing_id=swing_id, session_id=session_id, kind=kind,
        content_json=json.dumps(output),
        model=getattr(backend, "name", None),
    ))


def coach_swing(conn, backend, swing_id):
    context = context_mod.build_swing_context(conn, swing_id)
    return _generate(conn, backend, context, kind="swing",
                     swing_id=swing_id, session_id=None)


def coach_session(conn, backend, session_id):
    context = context_mod.build_session_context(conn, session_id)
    return _generate(conn, backend, context, kind="session",
                     swing_id=None, session_id=session_id)
