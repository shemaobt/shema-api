"""Undo one period's log - ``DELETE /api/shema/meetings/log/{meetingId}/{scopeKey}/{period}``.

``rhythmStore.undoMeeting`` in the console, and FE-44 §9.7's 204. The row is deleted, not
flagged: the log says a meeting happened, and a log undone says nothing - a tombstone would be a
second state for the console to learn and a record of a meeting that did not take place.

**The audience and the region are asked before the row is looked for**, so the answer to a
caller out of scope is the same 403 whether or not that period was ever logged. The period is
the one the server gave when the entry was written; it is matched as stored, and a period that
names nothing is a 404.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.services.shema import _meeting_log, _trail
from app.services.shema._scope import RegionScope
from app.utils.shema_meetings import MeetingScopeKey, ShemaMeetingId

logger = logging.getLogger(__name__)


async def undo_meeting(
    db: AsyncSession,
    scope: RegionScope,
    meeting_id: ShemaMeetingId,
    scope_key: MeetingScopeKey,
    period: str,
    *,
    actor: User,
    app_key: str,
) -> None:
    """Delete the entry of one meeting, region and period, or refuse without looking."""
    actor_id = actor.id
    await _meeting_log.require_reads_meetings(db, actor, app_key, operation="undo_meeting")
    region = _meeting_log.require_writes_region(scope, scope_key)

    row = await _meeting_log.find_log(db, meeting_id.value, region.value, period)
    if row is None:
        raise NotFoundError("No log for that meeting, region and period")

    _trail.stage(
        db,
        actor=actor,
        subject="meeting",
        action="removed",
        subject_id=f"{meeting_id.value}:{region.value}:{period}",
        region_key=_trail.region_value(region.value),
    )
    await db.delete(row)
    await db.commit()

    logger.info(
        "shema meeting log undone",
        extra={
            "shema_operation": "undo_meeting",
            "shema_user_id": actor_id,
            "shema_meeting_id": meeting_id.value,
            "shema_scope_key": region.value,
            "shema_period": period,
        },
    )
