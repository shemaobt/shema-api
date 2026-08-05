from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError
from app.db.models.phase import Phase, PhaseCategory
from app.models.phase import PhaseUpdate
from app.services.phase.get_phase_or_404 import get_phase_or_404


async def update_phase(db: AsyncSession, phase_id: str, payload: PhaseUpdate) -> Phase:
    phase = await get_phase_or_404(db, phase_id)
    if payload.name is not None:
        phase.name = payload.name
    if payload.description is not None:
        phase.description = payload.description
    if "category_id" in payload.model_fields_set:
        if payload.category_id is not None:
            category_result = await db.execute(
                select(PhaseCategory.id).where(PhaseCategory.id == payload.category_id)
            )
            if category_result.scalar_one_or_none() is None:
                raise UnknownReferenceError("This phase points at a category that does not exist")
        phase.category_id = payload.category_id
    if "icon_url" in payload.model_fields_set:
        phase.icon_url = payload.icon_url
    await db.commit()
    await db.refresh(phase)
    return phase
