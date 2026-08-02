from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, ProjectPhase
from app.db.models.project import Project
from app.models.phase import ProjectPhaseResponse


async def list_project_phases_with_details(
    db: AsyncSession,
    project_id: str,
) -> list[ProjectPhaseResponse]:
    journey_result = await db.execute(select(Project.journey_id).where(Project.id == project_id))
    journey_id = journey_result.scalar_one_or_none()

    stmt = select(Phase, ProjectPhase).outerjoin(
        ProjectPhase,
        and_(ProjectPhase.phase_id == Phase.id, ProjectPhase.project_id == project_id),
    )
    if journey_id is not None:
        stmt = stmt.where(Phase.journey_id == journey_id).order_by(
            Phase.sort_order, Phase.created_at
        )
    else:
        stmt = stmt.where(ProjectPhase.project_id == project_id).order_by(Phase.name)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        ProjectPhaseResponse(
            id=link.id if link is not None else phase.id,
            phase_id=phase.id,
            phase_name=phase.name,
            phase_description=phase.description,
            status=link.status if link is not None else "not_started",
        )
        for phase, link in rows
    ]
