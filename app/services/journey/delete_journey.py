from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.services.journey.get_journey_or_404 import get_journey_or_404


async def delete_journey(db: AsyncSession, journey_id: str) -> None:
    journey = await get_journey_or_404(db, journey_id)
    await db.execute(
        update(Project).where(Project.journey_id == journey_id).values(journey_id=None)
    )
    await db.delete(journey)
    await db.commit()
