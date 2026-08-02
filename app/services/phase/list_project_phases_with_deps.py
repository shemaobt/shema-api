from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import PhaseDependency
from app.models.phase import ProjectPhasesWithDepsResponse
from app.services.phase.list_project_phases_with_details import (
    list_project_phases_with_details,
)


async def list_project_phases_with_deps(
    db: AsyncSession,
    project_id: str,
) -> ProjectPhasesWithDepsResponse:
    phases = await list_project_phases_with_details(db, project_id)
    phase_ids = [p.phase_id for p in phases]

    deps_map: dict[str, list[str]] = {pid: [] for pid in phase_ids}
    if phase_ids:
        dep_stmt = (
            select(PhaseDependency)
            .where(PhaseDependency.phase_id.in_(phase_ids))
            .order_by(PhaseDependency.phase_id)
        )
        dep_result = await db.execute(dep_stmt)
        for dep in dep_result.scalars().all():
            if dep.phase_id in deps_map:
                deps_map[dep.phase_id].append(dep.depends_on_id)

    return ProjectPhasesWithDepsResponse(phases=phases, dependencies=deps_map)
