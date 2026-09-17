"""The one place a team's devices are counted.

The issue asks that the number the Desk shows beside a team and the length of this list
never disagree, and the way to keep a promise like that is to have one query rather than
two that happen to match today. Anything that needs a count takes it from here.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.device import Device


async def list_team_devices(db: AsyncSession, project_id: str) -> list[Device]:
    """Every device currently linked to ``project_id``, oldest link first.

    Unlinked devices are excluded here rather than by each caller. They keep their
    ``project_id`` so the row still records where the tablet was, which is exactly why the
    filter has to live in one place: a caller that forgot it would show tablets that have
    been taken out of service.
    """
    rows = await db.execute(
        select(Device)
        .where(Device.project_id == project_id, Device.unlinked_at.is_(None))
        .order_by(Device.claimed_at)
    )
    return list(rows.scalars().all())
