from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.public_request import PublicRequest


async def list_public_requests(
    db: AsyncSession, *, kind: str | None = None, status: str | None = None
) -> list[PublicRequest]:
    stmt: Select[tuple[PublicRequest]] = select(PublicRequest).order_by(
        PublicRequest.requested_at.desc()
    )
    if kind:
        stmt = stmt.where(PublicRequest.kind == kind)
    if status:
        stmt = stmt.where(PublicRequest.status == status)
    result = await db.execute(stmt)
    return list(result.scalars().all())
