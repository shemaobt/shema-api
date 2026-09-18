from sqlalchemy import and_, case, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, ProjectPhase
from app.db.models.project import Project
from app.models.phase import ProjectPhaseResponse


async def list_project_phases_with_details(
    db: AsyncSession,
    project_id: str,
) -> list[ProjectPhaseResponse]:
    """The journey's phase set unioned with whatever else is attached to the project.

    ``attach_phase_to_project`` never required the phase to belong to the project's journey, so
    filtering by journey alone would drop the rows that came from another journey or from none —
    and the status they already carry. The journey's own phases stay first, in journey order.
    """
    journey_result = await db.execute(select(Project.journey_id).where(Project.id == project_id))
    journey_id = journey_result.scalar_one_or_none()

    attached = ProjectPhase.id.is_not(None)
    stmt = select(Phase, ProjectPhase).outerjoin(
        ProjectPhase,
        and_(ProjectPhase.phase_id == Phase.id, ProjectPhase.project_id == project_id),
    )
    if journey_id is not None:
        in_journey = Phase.journey_id == journey_id
        stmt = stmt.where(or_(in_journey, attached)).order_by(
            case((in_journey, 0), else_=1), Phase.sort_order, Phase.created_at
        )
    else:
        stmt = stmt.where(attached).order_by(Phase.name)
    result = await db.execute(stmt)
    rows = result.all()
    return [
        ProjectPhaseResponse(
            id=link.id if link is not None else None,
            phase_id=phase.id,
            phase_name=phase.name,
            phase_description=phase.description,
            status=link.status if link is not None else "not_started",
        )
        for phase, link in rows
    ]
