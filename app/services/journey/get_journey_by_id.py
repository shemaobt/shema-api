from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journey import Journey


async def get_journey_by_id(db: AsyncSession, journey_id: str) -> Journey | None:
    stmt: Select[tuple[Journey]] = select(Journey).where(Journey.id == journey_id)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
