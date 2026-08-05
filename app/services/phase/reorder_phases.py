from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError
from app.db.models.phase import Phase


async def reorder_phases(db: AsyncSession, journey_id: str, phase_ids: list[str]) -> None:
    from app.services.journey.get_journey_by_id import get_journey_by_id

    if await get_journey_by_id(db, journey_id) is None:
        raise UnknownReferenceError("This reorder points at a journey that does not exist")
    result = await db.execute(select(Phase).where(Phase.journey_id == journey_id))
    phases = {phase.id: phase for phase in result.scalars().all()}
    if len(phase_ids) != len(set(phase_ids)) or set(phase_ids) != set(phases):
        raise UnknownReferenceError("Phase ids must match exactly the journey's phases")
    for position, phase_id in enumerate(phase_ids):
        phases[phase_id].sort_order = position
    await db.commit()
