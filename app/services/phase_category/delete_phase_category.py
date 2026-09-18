from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.phase import Phase, PhaseCategory
from app.services.phase_category.get_phase_category_or_404 import get_phase_category_or_404


async def delete_phase_category(db: AsyncSession, category_id: str) -> None:
    category = await get_phase_category_or_404(db, category_id)

    total_result = await db.execute(select(func.count(PhaseCategory.id)))
    if total_result.scalar_one() <= 1:
        raise ConflictError("At least one category is required")

    oldest_result = await db.execute(
        select(PhaseCategory)
        .where(PhaseCategory.id != category_id)
        .order_by(PhaseCategory.created_at, PhaseCategory.id)
        .limit(1)
    )
    fallback = oldest_result.scalar_one()

    await db.execute(
        update(Phase).where(Phase.category_id == category_id).values(category_id=fallback.id)
    )
    await db.delete(category)
    await db.commit()
