from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import PhaseCategory
from app.models.journey import PhaseCategoryCreate


async def create_phase_category(db: AsyncSession, payload: PhaseCategoryCreate) -> PhaseCategory:
    category = PhaseCategory(name=payload.name, color=payload.color, icon=payload.icon)
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category
