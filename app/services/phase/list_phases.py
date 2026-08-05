from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, ProjectPhase


async def list_phases(
    db: AsyncSession,
    project_id: str | None = None,
    journey_id: str | None = None,
) -> list[Phase]:
    if project_id is not None:
        stmt = (
            select(Phase)
            .join(ProjectPhase, ProjectPhase.phase_id == Phase.id)
            .where(ProjectPhase.project_id == project_id)
        )
    else:
        stmt = select(Phase)
    if journey_id is not None:
        stmt = stmt.where(Phase.journey_id == journey_id)
    stmt = stmt.order_by(Phase.sort_order, Phase.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
