from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.phase import PhaseStatus, ProjectPhase


async def update_project_phase_status(
    db: AsyncSession,
    project_id: str,
    phase_id: str,
    status: PhaseStatus,
) -> ProjectPhase:
    stmt = select(ProjectPhase).where(
        ProjectPhase.project_id == project_id,
        ProjectPhase.phase_id == phase_id,
    )
    result = await db.execute(stmt)
    link = result.scalar_one_or_none()
    if not link:
        raise NotFoundError("Phase is not attached to this project")
    link.status = status
    await db.commit()
    await db.refresh(link)
    return link
