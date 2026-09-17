from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.sound_necklace import AuditEvent, SnAuditEvent


async def list_audit_events(
    db: AsyncSession,
    project_id: str,
    *,
    since: datetime | None = None,
    until: datetime | None = None,
    event: AuditEvent | None = None,
    limit: int = 100,
) -> list[SnAuditEvent]:
    """One project's audit trail, newest first.

    Scoped to the project in the statement, not filtered afterwards: this log names who
    reached whose voice, and a query that could return another project's rows would be a
    leak of exactly the thing it is meant to protect.

    ``since`` and ``until`` bound the window as ``[since, until)``. Without an upper bound
    the newest-first view can only be read from the current end — raising ``since`` strips
    older rows but never reaches a past window once it is more than ``limit`` events back.
    """
    stmt = select(SnAuditEvent).where(SnAuditEvent.project_id == project_id)
    if since is not None:
        stmt = stmt.where(SnAuditEvent.occurred_at >= since)
    if until is not None:
        stmt = stmt.where(SnAuditEvent.occurred_at < until)
    if event is not None:
        stmt = stmt.where(SnAuditEvent.event == event)
    # id breaks the tie: two events in the same instant would otherwise come back in
    # whatever order the scan produced, and a paging auditor would see one twice or never.
    # DESC on both, matching the index's column order — the tiebreak direction is
    # arbitrary, but a mixed one (DESC, ASC) cannot be read off the index and makes
    # Postgres sort every one of a project's events before the LIMIT can take a hundred.
    stmt = stmt.order_by(SnAuditEvent.occurred_at.desc(), SnAuditEvent.id.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars().all())
