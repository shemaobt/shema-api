"""What kind of halt a session is in, and what kind its last one was.

Two readings of the halt columns, in one place because four readers need them and the day
they drift is the day the tablet and the Desk disagree about whether a room is stopped.

**They are different questions.** ``standing`` is what the tablet and the Desk ask: it must be
null the moment no halt stands — one signal, not two. ``last`` is what a facilitator asks
afterwards: a halt lifted before anybody saw it would otherwise vanish without trace, and the
team's history is where that must not happen.

**The two kinds stand in different places** (ENG-1163, ADR 0039). A blocking halt is the
status ``needs_person``: the room cannot go on. A warning refuses nothing, so it never touches
the status; it stands from ``warned_at`` until a facilitator attends the session, and undoing
that visit brings it back. A blocking halt over a standing warning answers ``blocking``, and the
warning answers again once the blocking halt is lifted.

Both answer ``HaltKind`` rather than a bare string, so the vocabulary travels in the type the
way ``SessionState`` does beside it on the Desk's card. A ``StrEnum`` serialises as the same
word, so nothing on the wire changes; what changes is that a caller cannot invent a third
kind by spelling one. The column is read back through the enum, which refuses a value no
writer here could have produced rather than serving it on.

A row halted before ENG-609 has no recorded kind and is answered ``blocking``. That is the
conservative reading — treating an unknown halt as one that stops the room sends somebody to
a team that did not need them, and the other way round leaves a stopped room waiting.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import ColumnElement, and_, case, literal

from app.core.room_enums import HaltKind
from app.db.models.internalization_room import IRSession, IRSessionStatus


def last(session: IRSession) -> HaltKind | None:
    """The kind of the most recent halt, whether or not it is still standing.

    Null means no halt this session can still name — which is no halt at all on any row
    written since ENG-609, and also a pre-ENG-609 halt that was already lifted. A halt with
    no kind on the row is
    only knowable as one while it stands, so a lifted halt from before ENG-609 reads as no
    halt at all — there is nothing on the row to say otherwise, and guessing here would put
    a blocking halt in the history of a conversation that may never have had one.
    """
    if session.halt_kind is not None:
        return HaltKind(session.halt_kind)
    if session.status is IRSessionStatus.NEEDS_PERSON:
        return HaltKind.BLOCKING
    return None


def standing(session: IRSession) -> HaltKind | None:
    """The kind of the halt in force right now, null when none is."""
    if session.status is IRSessionStatus.NEEDS_PERSON:
        return HaltKind.BLOCKING
    if warned_at(session) is not None:
        return HaltKind.WARNING
    return None


def warned_at(session: IRSession) -> datetime | None:
    if session.attended_at is not None:
        return None
    return session.warned_at


def a_lift_restores() -> ColumnElement[IRSessionStatus]:
    return case(
        (IRSession.ended_at.is_not(None), literal(IRSessionStatus.DONE, IRSession.status.type)),
        else_=literal(IRSessionStatus.IN_PROGRESS, IRSession.status.type),
    )


def a_warning_stands() -> ColumnElement[bool]:
    """``standing``'s warning, as a clause for the queue that lists the rooms under one."""
    return and_(IRSession.warned_at.is_not(None), IRSession.attended_at.is_(None))
