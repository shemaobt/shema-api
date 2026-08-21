from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journey import Journey
from app.models.journey import JourneyUpdate
from app.services.journey.get_journey_or_404 import get_journey_or_404


async def update_journey(db: AsyncSession, journey_id: str, payload: JourneyUpdate) -> Journey:
    journey = await get_journey_or_404(db, journey_id)
    if payload.name is not None:
        journey.name = payload.name
    if payload.description is not None:
        journey.description = payload.description
    await db.commit()
    await db.refresh(journey)
    return journey
