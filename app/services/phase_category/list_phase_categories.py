from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, PhaseCategory
from app.models.journey import PhaseCategoryResponse


async def list_phase_categories(db: AsyncSession) -> list[PhaseCategoryResponse]:
    result = await db.execute(
        select(PhaseCategory).order_by(PhaseCategory.created_at, PhaseCategory.id)
    )
    categories = list(result.scalars().all())

    counts_result = await db.execute(
        select(Phase.category_id, func.count(Phase.id))
        .where(Phase.category_id.is_not(None))
        .group_by(Phase.category_id)
    )
    counts: dict[str | None, int] = {
        category_id: count for category_id, count in counts_result.all()
    }

    return [
        PhaseCategoryResponse(
            id=category.id,
            name=category.name,
            color=category.color,
            icon=category.icon,
            phase_count=counts.get(category.id, 0),
        )
        for category in categories
    ]
