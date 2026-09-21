from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase
from app.db.models.project import Project
from app.models.journey import JourneyResponse
from app.services.journey.get_journey_or_404 import get_journey_or_404


async def get_journey_with_counts(db: AsyncSession, journey_id: str) -> JourneyResponse:
    journey = await get_journey_or_404(db, journey_id)

    phase_count_result = await db.execute(
        select(func.count(Phase.id)).where(Phase.journey_id == journey_id)
    )
    phase_count = phase_count_result.scalar_one()

    project_count_result = await db.execute(
        select(func.count(Project.id)).where(Project.journey_id == journey_id)
    )
    project_count = project_count_result.scalar_one()

    return JourneyResponse(
        id=journey.id,
        name=journey.name,
        description=journey.description,
        created_by=journey.created_by,
        created_at=journey.created_at,
        updated_at=journey.updated_at,
        phase_count=phase_count,
        project_count=project_count,
    )
