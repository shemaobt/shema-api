from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, PhaseDependency, ProjectPhase
from app.db.models.project import Project
from app.models.phase import PhaseResponse, PhasesWithDepsResponse


async def list_phases_by_projects(
    db: AsyncSession,
    project_ids: list[str],
    project_id: str | None = None,
    journey_id: str | None = None,
) -> list[Phase]:
    if not project_ids:
        return []
    scoped_project_ids = project_ids
    if project_id is not None:
        if project_id not in project_ids:
            return []
        scoped_project_ids = [project_id]
    journey_ids_subq = (
        select(Project.journey_id)
        .where(Project.id.in_(scoped_project_ids), Project.journey_id.is_not(None))
        .distinct()
    )
    linked_phase_ids_subq = (
        select(ProjectPhase.phase_id)
        .join(Project, Project.id == ProjectPhase.project_id)
        .where(ProjectPhase.project_id.in_(scoped_project_ids), Project.journey_id.is_(None))
        .distinct()
    )
    stmt = select(Phase).where(
        or_(Phase.journey_id.in_(journey_ids_subq), Phase.id.in_(linked_phase_ids_subq))
    )
    if journey_id is not None:
        stmt = stmt.where(Phase.journey_id == journey_id)
    stmt = stmt.order_by(Phase.sort_order, Phase.created_at)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def list_phases_with_deps_by_projects(
    db: AsyncSession,
    project_ids: list[str],
) -> PhasesWithDepsResponse:
    phases = await list_phases_by_projects(db, project_ids)
    if not phases:
        return PhasesWithDepsResponse(phases=[], dependencies={})

    phase_ids = [p.id for p in phases]
    deps_result = await db.execute(
        select(PhaseDependency).where(
            PhaseDependency.phase_id.in_(phase_ids),
            PhaseDependency.depends_on_id.in_(phase_ids),
        )
    )
    all_deps = list(deps_result.scalars().all())

    deps_map: dict[str, list[str]] = {p.id: [] for p in phases}
    for dep in all_deps:
        if dep.phase_id in deps_map:
            deps_map[dep.phase_id].append(dep.depends_on_id)

    return PhasesWithDepsResponse(
        phases=[PhaseResponse.model_validate(p) for p in phases],
        dependencies=deps_map,
    )
