from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.journey import Journey
from app.db.models.phase import Phase
from app.db.models.project import Project
from app.models.journey import JourneyResponse


async def list_journeys(db: AsyncSession) -> list[JourneyResponse]:
    result = await db.execute(select(Journey).order_by(Journey.created_at, Journey.id))
    journeys = list(result.scalars().all())

    phase_counts_result = await db.execute(
        select(Phase.journey_id, func.count(Phase.id))
        .where(Phase.journey_id.is_not(None))
        .group_by(Phase.journey_id)
    )
    phase_counts: dict[str | None, int] = dict(phase_counts_result.tuples().all())

    project_counts_result = await db.execute(
        select(Project.journey_id, func.count(Project.id))
        .where(Project.journey_id.is_not(None))
        .group_by(Project.journey_id)
    )
    project_counts: dict[str | None, int] = dict(project_counts_result.tuples().all())

    return [
        JourneyResponse(
            id=journey.id,
            name=journey.name,
            description=journey.description,
            created_by=journey.created_by,
            created_at=journey.created_at,
            updated_at=journey.updated_at,
            phase_count=phase_counts.get(journey.id, 0),
            project_count=project_counts.get(journey.id, 0),
        )
        for journey in journeys
    ]
