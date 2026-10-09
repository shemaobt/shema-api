from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only

from app.db.models.internalization_room import IRSession
from app.services.internalization_room.coverage import is_panorama
from app.services.internalization_room.entered import entered
from app.services.internalization_room.live import live
from app.services.internalization_room.session_end import SessionState, end_of


async def holding(db: AsyncSession, now: datetime, window: timedelta) -> list[IRSession]:
    result = await db.execute(
        select(IRSession)
        .options(
            load_only(
                IRSession.project_id,
                IRSession.pericope,
                IRSession.created_at,
                IRSession.ended_at,
                IRSession.updated_at,
            )
        )
        .where(
            IRSession.project_id.is_not(None),
            live(),
            entered(),
            IRSession.updated_at >= now - window,
        )
    )
    return [
        session
        for session in result.scalars()
        if not is_panorama(session.pericope) and end_of(session).state is SessionState.IN_PROGRESS
    ]
