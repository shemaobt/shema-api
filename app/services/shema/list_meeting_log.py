"""The Rhythm's log, as far as the caller reaches - ``GET /api/shema/meetings/log``.

FE-44 §9.7 takes no parameters and the console hydrates its whole store from this read, so it
answers every entry the caller may see. **No limit, deliberately**: the log holds one row per
meeting, region and period, which is at most 84 a year for the three meetings of the set in the
seven regions, and a cut-off would drop the entries the console reads *overdue* from.

Newest meeting first, then by meeting and region, so the order is stable between two calls.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_meeting import ShemaMeetingLogEntry
from app.models.shema_meeting import MeetingLogEntry
from app.services.shema._meeting_log import logs_within, require_reads_meetings
from app.services.shema._scope import RegionScope


async def list_meeting_log(
    db: AsyncSession, scope: RegionScope, *, reader: User, app_key: str
) -> list[MeetingLogEntry]:
    """Every entry in the caller's scope, for an account in the log's audience."""
    await require_reads_meetings(db, reader, app_key, operation="list_meeting_log")

    stmt = (
        select(ShemaMeetingLogEntry)
        .where(logs_within(scope))
        .order_by(
            ShemaMeetingLogEntry.meeting_date.desc(),
            ShemaMeetingLogEntry.meeting_id,
            ShemaMeetingLogEntry.scope_key,
        )
    )
    return [MeetingLogEntry.of(row) for row in (await db.execute(stmt)).scalars()]
