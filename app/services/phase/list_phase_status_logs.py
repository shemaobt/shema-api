from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.phase import PhaseStatusLog
from app.models.journey import PhaseStatusLogResponse


async def list_phase_status_logs(
    db: AsyncSession,
    project_id: str,
    phase_id: str | None = None,
) -> list[PhaseStatusLogResponse]:
    stmt = (
        select(PhaseStatusLog, User)
        .outerjoin(User, PhaseStatusLog.changed_by == User.id)
        .where(PhaseStatusLog.project_id == project_id)
    )
    if phase_id is not None:
        stmt = stmt.where(PhaseStatusLog.phase_id == phase_id)
    stmt = stmt.order_by(PhaseStatusLog.created_at.desc())
    result = await db.execute(stmt)
    return [
        PhaseStatusLogResponse(
            id=log.id,
            project_id=log.project_id,
            phase_id=log.phase_id,
            from_status=log.from_status,
            to_status=log.to_status,
            note=log.note,
            changed_by=log.changed_by,
            changed_by_name=(author.display_name or author.email) if author else None,
            is_admin_author=bool(author and author.is_platform_admin),
            created_at=log.created_at,
        )
        for log, author in result.all()
    ]
