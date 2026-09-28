"""The Rhythm's log on the wire - FE-44 §5.4's ``MeetingLogEntry``, and what ``POST`` accepts.

``MeetingLogEntry`` is frozen as ``{meetingId, scopeKey, period, date, notes}`` and is reproduced
here key for key: a record that a meeting of one period happened in one scope, not an agenda.
There is no series, no occurrence, no hour and no timezone, because the frozen model has none -
``date`` is a calendar day somebody wrote down (FE-44 §9.0).

**The request has no** ``period`` **and refuses one.** FE-44 §9.7's body is ``{meetingId,
scopeKey, date, notes}``, and the period is the server's to derive from the day and the
meeting's cadence (``app/utils/shema_derivations.py``). ``extra="forbid"`` makes *the client
cannot state the period* a property of the shape: a body that carries one is a 422, not a value
quietly ignored or, worse, trusted.

**The day is read by field.** :data:`MeetingDay` runs ``parse_iso_date`` before Pydantic's own
``date``, which on its own accepts a unix timestamp and a datetime with an offset. It is also the
alias that lets the field be called ``date`` without shadowing its own annotation - the ``Day``
mechanism of ``app/models/shema_health.py``.

**Not a** ``LeavingShape``: nothing here names a place. ``scopeKey`` is the coarse region key
every ``RegionScope`` already answers in the clear, the same distinction
``app/models/shema_notification.py`` draws for its ``region``.

``ShemaMeetingId`` and ``MeetingScopeKey`` are re-exported so ``app/api/shema/meetings.py`` types
its path parameters from here rather than from ``app.utils`` and ``app.db.models`` - the layering
``tests/test_shema/test_layering.py`` keeps.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from pydantic import AliasGenerator, BaseModel, BeforeValidator, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.db.models.shema_meeting import ShemaMeetingLogEntry
from app.utils.shema_derivations import parse_iso_date
from app.utils.shema_meetings import MeetingScopeKey as MeetingScopeKey
from app.utils.shema_meetings import ShemaMeetingId as ShemaMeetingId

#: A calendar day on the way out. An alias, because a field called ``date`` annotated ``date``
#: shadows its own annotation and Pydantic cannot build the model.
Day = date

#: A calendar day off the wire, ``YYYY-MM-DD`` and nothing wider.
MeetingDay = Annotated[date, BeforeValidator(parse_iso_date)]

#: The ceiling on one log's notes. Not a product rule - a bound on a write, generous against
#: the minutes of a meeting typed into a dialog and small against a runaway payload.
MAX_NOTES_LENGTH = 10_000

_INWARD = ConfigDict(
    extra="forbid",
    populate_by_name=True,
    alias_generator=AliasGenerator(validation_alias=to_camel),
)

_OUTWARD = ConfigDict(
    populate_by_name=True,
    alias_generator=AliasGenerator(serialization_alias=to_camel),
)


class MeetingLogCreate(BaseModel):
    """What ``POST /api/shema/meetings/log`` accepts - FE-44 §9.7's body, and no ``period``."""

    model_config = _INWARD

    meeting_id: ShemaMeetingId
    scope_key: MeetingScopeKey
    date: MeetingDay
    notes: str = Field(default="", max_length=MAX_NOTES_LENGTH)


class MeetingLogEntry(BaseModel):
    """One meeting, logged once for one scope and one period. **Frozen** - FE-44 §5.4.

    ``meetingId`` and ``scopeKey`` are plain text on the way out rather than the request's
    closed types: a row is what was stored, and a set changed later must not make yesterday's
    rows unreadable as a 500.
    """

    model_config = _OUTWARD

    meeting_id: str
    scope_key: str
    period: str
    date: Day
    notes: str

    @classmethod
    def of(cls, row: ShemaMeetingLogEntry) -> MeetingLogEntry:
        """Build from the row, field for field.

        ``created_at`` and ``updated_at`` are never read here: they are set by the database, so
        after a flush they are expired, and touching one would be an implicit lazy load on an
        async session.
        """
        return cls(
            meeting_id=row.meeting_id,
            scope_key=row.scope_key,
            period=row.period,
            date=row.meeting_date,
            notes=row.notes,
        )
