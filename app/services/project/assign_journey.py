from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, ProjectPhase
from app.db.models.project import Project
from app.services.project.get_project_or_404 import get_project_or_404


async def assign_journey(db: AsyncSession, project_id: str, journey_id: str | None) -> Project:
    from app.services.journey.get_journey_or_404 import get_journey_or_404

    project = await get_project_or_404(db, project_id)
    if journey_id is not None:
        await get_journey_or_404(db, journey_id)
    project.journey_id = journey_id
    if journey_id is None:
        await db.execute(delete(ProjectPhase).where(ProjectPhase.project_id == project_id))
    else:
        journey_phase_ids = select(Phase.id).where(Phase.journey_id == journey_id)
        await db.execute(
            delete(ProjectPhase).where(
                ProjectPhase.project_id == project_id,
                ProjectPhase.phase_id.not_in(journey_phase_ids),
            )
        )
    await db.commit()
    await db.refresh(project)
    return project
