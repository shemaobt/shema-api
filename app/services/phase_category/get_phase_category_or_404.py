from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import PhaseCategory
from app.services.common import get_or_raise


async def get_phase_category_or_404(db: AsyncSession, category_id: str) -> PhaseCategory:
    return await get_or_raise(db, PhaseCategory, category_id, label="Phase category")
