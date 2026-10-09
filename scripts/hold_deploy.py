from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession


async def holding(db: AsyncSession, now: datetime, window: timedelta) -> list[IRSession]:
    result = await db.execute(select(IRSession).where(IRSession.project_id.is_not(None)))
    return list(result.scalars())
