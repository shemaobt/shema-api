"""Record that a meeting happened - ``POST /api/shema/meetings/log``, ``rhythmStore.logMeeting``.

**The server derives the period, and a second log of the same period replaces the first.** Both
are FE-44 §9.7 in one sentence each. The day and the meeting's cadence give the period by field
(``app/utils/shema_derivations.py``); ``(meeting_id, scope_key, period)`` is unique in the table,
and a log that lands on an existing key rewrites that row's day and notes instead of adding a
second one. It is a record that the listening happened, not an agenda: there is no series and no
occurrence to keep apart.

**The unique constraint is the arbiter, not the read.** The write reads the key's row, then
creates or updates it inside a savepoint. Two coordinators logging the same period at once both
read *nothing*; the second insert then conflicts on the constraint, and instead of a 500 the
write is retried once as the replacement it is. The mirror race - an undo deleting the row
between the read and the update - surfaces as ``StaleDataError`` and is retried the same way, as
a fresh insert. A second failure is raised: two collisions in a row are not the race this
handles. The shape is portable on purpose - the suite runs on SQLite and production on
PostgreSQL, which is ``mark_notifications_read.py``'s argument against a dialect's ``ON
CONFLICT`` - and the savepoint is ``app/services/device/refresh_claim_code.py``'s: undoing a
failed attempt must not expire what the session already holds, and every write sits inside it.

**A day that has not come yet is refused.** A log says the meeting took place; one dated next
week would mark a period *done* before anybody met. The bound is the UTC day plus one - the
window ``app/api/shema/projects.py`` gives ``X-Shema-Local-Date``, which every real offset fits
in - so a coordinator in UTC+14 logging this morning's meeting is never refused.

**Who wrote it lives in the log line**, not in a column: the frozen ``MeetingLogEntry`` has no
author, and the line names the account, the key and whether a row was replaced. Never the
notes - they are a pastoral reading of a team, and a log is kept longer and read wider than the
row.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import NamedTuple

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.exc import StaleDataError

from app.core.exceptions import UnprocessableValueError
from app.db.models.auth import User
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.db.models.shema_meeting import ShemaMeetingLogEntry
from app.models.shema_meeting import MeetingLogCreate, MeetingLogEntry
from app.services.shema import _meeting_log, _trail
from app.services.shema._scope import RegionScope
from app.utils.shema_derivations import period_key
from app.utils.shema_meetings import MEETING_CADENCES

logger = logging.getLogger(__name__)

#: One retry: enough for the one concurrent write the constraint can reveal.
_ATTEMPTS = 2


class LoggedMeeting(NamedTuple):
    """The entry as stored, and whether it replaced one already there - 200 rather than 201."""

    entry: MeetingLogEntry
    replaced: bool


async def log_meeting(
    db: AsyncSession,
    scope: RegionScope,
    payload: MeetingLogCreate,
    *,
    actor: User,
    app_key: str,
    today: date,
) -> LoggedMeeting:
    """Log one meeting for one region, deriving its period; replace the period's entry if any."""
    actor_id = actor.id
    await _meeting_log.require_reads_meetings(db, actor, app_key, operation="log_meeting")
    region = _meeting_log.require_writes_region(scope, payload.scope_key)
    if payload.date > today + timedelta(days=1):
        raise UnprocessableValueError(
            f"date: {payload.date.isoformat()} has not happened yet, and the log records a "
            "meeting that took place"
        )

    meeting_id = payload.meeting_id.value
    period = period_key(MEETING_CADENCES[payload.meeting_id], payload.date)

    for _ in range(_ATTEMPTS - 1):
        try:
            row, replaced = await _write_once(db, meeting_id, region.value, period, payload)
            break
        except (IntegrityError, StaleDataError):
            continue
    else:
        row, replaced = await _write_once(db, meeting_id, region.value, period, payload)

    _trail.stage(
        db,
        actor=actor,
        subject=ChangeSubject.MEETING,
        action=ChangeAction.REPLACED if replaced else ChangeAction.CREATED,
        subject_id=f"{meeting_id}:{region.value}:{period}",
        region_key=_trail.region_value(region.value),
        fields=("date", "notes"),
    )
    await db.commit()
    entry = MeetingLogEntry.of(row)

    logger.info(
        "shema meeting logged",
        extra={
            "shema_operation": "log_meeting",
            "shema_user_id": actor_id,
            "shema_meeting_id": meeting_id,
            "shema_scope_key": region.value,
            "shema_period": period,
            "shema_replaced": replaced,
        },
    )
    return LoggedMeeting(entry=entry, replaced=replaced)


async def _write_once(
    db: AsyncSession, meeting_id: str, scope_key: str, period: str, payload: MeetingLogCreate
) -> tuple[ShemaMeetingLogEntry, bool]:
    """One attempt: read the key's row, then create or rewrite it inside a savepoint.

    Every write is inside the block, and the block is the last write before the caller commits:
    ``begin_nested`` flushes whatever is already dirty on the way in, and on SQLite a savepoint
    opened before any other write is the transaction itself (ADR 0031). A failed attempt rolls
    back to the savepoint, which discards the row it added and leaves the session usable.
    """
    existing = await _meeting_log.find_log(db, meeting_id, scope_key, period)
    row = existing or ShemaMeetingLogEntry(
        meeting_id=meeting_id, scope_key=scope_key, period=period
    )
    async with db.begin_nested():
        if existing is None:
            db.add(row)
        row.meeting_date = payload.date
        row.notes = payload.notes
    return row, existing is not None
