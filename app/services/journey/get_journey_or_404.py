from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journey import Journey
from app.services.common import get_or_raise


async def get_journey_or_404(db: AsyncSession, journey_id: str) -> Journey:
    return await get_or_raise(db, Journey, journey_id, label="Journey")
