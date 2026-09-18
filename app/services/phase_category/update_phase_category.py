from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import PhaseCategory
from app.models.journey import PhaseCategoryUpdate
from app.services.phase_category.get_phase_category_or_404 import get_phase_category_or_404


async def update_phase_category(
    db: AsyncSession,
    category_id: str,
    payload: PhaseCategoryUpdate,
) -> PhaseCategory:
    category = await get_phase_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name
    if payload.color is not None:
        category.color = payload.color
    if payload.icon is not None:
        category.icon = payload.icon
    await db.commit()
    await db.refresh(category)
    return category
