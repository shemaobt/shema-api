from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journey import Journey
from app.models.journey import JourneyCreate


async def create_journey(
    db: AsyncSession,
    payload: JourneyCreate,
    *,
    created_by: str | None = None,
) -> Journey:
    journey = Journey(
        name=payload.name,
        description=payload.description,
        created_by=created_by,
    )
    db.add(journey)
    await db.commit()
    await db.refresh(journey)
    return journey
