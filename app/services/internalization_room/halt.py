"""What kind of halt a session is in, and what kind its last one was.

Two readings of one column, in one place because three readers need them and the day they
drift is the day the tablet and the Desk disagree about whether a room is stopped.

**They are different questions.** ``standing`` is what the tablet asks: it halts on the
answer, so it must be null the moment the halt is gone — one signal, not two. ``last`` is
what a facilitator asks afterwards: a warning lifted by a landing turn before anybody saw it
would otherwise vanish without trace, and the team's history is where that must not happen.

A row halted before ENG-609 has no recorded kind and is answered ``blocking``. That is the
conservative reading — treating an unknown halt as one that stops the room sends somebody to
a team that did not need them, and the other way round leaves a stopped room waiting.
"""

from __future__ import annotations

from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSession, IRSessionStatus


def last(session: IRSession) -> str | None:
    """The kind of the most recent halt, whether or not it is still standing.

    Null means no halt this session can still name — which is no halt at all on any row
    written since ENG-609, and also a pre-ENG-609 halt that was already lifted. A halt with
    no kind on the row is
    only knowable as one while it stands, so a lifted halt from before ENG-609 reads as no
    halt at all — there is nothing on the row to say otherwise, and guessing here would put
    a blocking halt in the history of a conversation that may never have had one.
    """
    if session.halt_kind is not None:
        return session.halt_kind
    if session.status is IRSessionStatus.NEEDS_PERSON:
        return HaltKind.BLOCKING.value
    return None


def standing(session: IRSession) -> str | None:
    """The kind of the halt in force right now, null when the room is not halted."""
    return last(session) if session.status is IRSessionStatus.NEEDS_PERSON else None
