from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase
from app.models.journey import PhaseCategoryResponse
from app.services.phase_category.get_phase_category_or_404 import get_phase_category_or_404


async def get_phase_category_with_count(
    db: AsyncSession,
    category_id: str,
) -> PhaseCategoryResponse:
    category = await get_phase_category_or_404(db, category_id)
    count_result = await db.execute(
        select(func.count(Phase.id)).where(Phase.category_id == category_id)
    )
    return PhaseCategoryResponse(
        id=category.id,
        name=category.name,
        color=category.color,
        icon=category.icon,
        phase_count=count_result.scalar_one(),
    )
