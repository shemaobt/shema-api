from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError
from app.db.models.phase import Phase, PhaseCategory
from app.models.phase import PhaseCreate


async def create_phase(db: AsyncSession, payload: PhaseCreate) -> Phase:
    from app.services.journey.get_journey_by_id import get_journey_by_id

    journey = await get_journey_by_id(db, payload.journey_id)
    if journey is None:
        raise UnknownReferenceError("This phase points at a journey that does not exist")
    if payload.category_id is not None:
        category_result = await db.execute(
            select(PhaseCategory.id).where(PhaseCategory.id == payload.category_id)
        )
        if category_result.scalar_one_or_none() is None:
            raise UnknownReferenceError("This phase points at a category that does not exist")
    max_result = await db.execute(
        select(func.max(Phase.sort_order)).where(Phase.journey_id == payload.journey_id)
    )
    max_sort_order = max_result.scalar_one_or_none()
    phase = Phase(
        name=payload.name,
        description=payload.description,
        journey_id=payload.journey_id,
        category_id=payload.category_id,
        sort_order=(max_sort_order if max_sort_order is not None else -1) + 1,
    )
    db.add(phase)
    await db.commit()
    await db.refresh(phase)
    return phase
