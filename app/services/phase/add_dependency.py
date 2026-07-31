from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.phase import PhaseDependency
from app.services.phase.get_phase_or_404 import get_phase_or_404


async def add_dependency(
    db: AsyncSession,
    phase_id: str,
    depends_on_id: str,
) -> PhaseDependency:
    await get_phase_or_404(db, phase_id)
    await get_phase_or_404(db, depends_on_id)
    if phase_id == depends_on_id:
        raise ConflictError("Phase cannot depend on itself")
    existing: Select[tuple[PhaseDependency]] = select(PhaseDependency).where(
        PhaseDependency.phase_id == phase_id,
        PhaseDependency.depends_on_id == depends_on_id,
    )
    result = await db.execute(existing)
    if result.scalar_one_or_none():
        raise ConflictError("Dependency already exists")
    all_deps_result = await db.execute(
        select(PhaseDependency.phase_id, PhaseDependency.depends_on_id)
    )
    edges: dict[str, list[str]] = {}
    for from_id, to_id in all_deps_result.all():
        edges.setdefault(from_id, []).append(to_id)
    stack = [depends_on_id]
    seen: set[str] = set()
    while stack:
        current = stack.pop()
        if current == phase_id:
            raise ConflictError("Dependency would create a cycle")
        if current in seen:
            continue
        seen.add(current)
        stack.extend(edges.get(current, []))
    dep = PhaseDependency(phase_id=phase_id, depends_on_id=depends_on_id)
    db.add(dep)
    await db.commit()
    await db.refresh(dep)
    return dep
