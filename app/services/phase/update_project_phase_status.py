from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import UnknownReferenceError
from app.db.models.auth import User
from app.db.models.phase import PhaseStatusLog, ProjectPhase

ALLOWED_PHASE_STATUSES = (
    "not_started",
    "in_progress",
    "delayed",
    "blocked",
    "completed",
    "cancelled",
)
NOTE_REQUIRED_STATUSES = ("delayed", "blocked", "cancelled")


async def update_project_phase_status(
    db: AsyncSession,
    project_id: str,
    phase_id: str,
    user: User,
    *,
    status: str,
    note: str | None = None,
) -> ProjectPhase:
    from app.services.oral_collector.require_manager import require_project_manager
    from app.services.phase.get_phase_or_404 import get_phase_or_404
    from app.services.project.get_project_or_404 import get_project_or_404

    project = await get_project_or_404(db, project_id)
    phase = await get_phase_or_404(db, phase_id)
    await require_project_manager(
        db,
        project_id,
        user.id,
        action="update phase status",
        is_platform_admin=user.is_platform_admin,
    )
    if status not in ALLOWED_PHASE_STATUSES:
        raise UnknownReferenceError(
            f"Invalid status '{status}'. Valid statuses are: {', '.join(ALLOWED_PHASE_STATUSES)}"
        )
    normalized_note = note.strip() if note and note.strip() else None
    if status in NOTE_REQUIRED_STATUSES and normalized_note is None:
        raise UnknownReferenceError(f"A note is required for status '{status}'")
    if phase.journey_id != project.journey_id:
        raise UnknownReferenceError("Phase does not belong to this project's journey")

    result = await db.execute(
        select(ProjectPhase).where(
            ProjectPhase.project_id == project_id,
            ProjectPhase.phase_id == phase_id,
        )
    )
    link = result.scalar_one_or_none()
    from_status = link.status if link else "not_started"
    if link is None:
        link = ProjectPhase(project_id=project_id, phase_id=phase_id, status=status)
        db.add(link)
    else:
        link.status = status
    log = PhaseStatusLog(
        project_id=project_id,
        phase_id=phase_id,
        from_status=from_status,
        to_status=status,
        note=normalized_note,
        changed_by=user.id,
    )
    db.add(log)
    await db.commit()
    await db.refresh(link)
    return link
