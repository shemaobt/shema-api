from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.change_request import ChangeRequest, ChangeRequestKind, ChangeRequestStatus


async def list_change_requests(
    db: AsyncSession,
    kind: ChangeRequestKind | None = None,
    status: ChangeRequestStatus | None = None,
) -> list[tuple[ChangeRequest, User]]:
    stmt = select(ChangeRequest, User).join(User, User.id == ChangeRequest.requester_user_id)
    if kind:
        stmt = stmt.where(ChangeRequest.kind == kind)
    if status:
        stmt = stmt.where(ChangeRequest.status == status)
    stmt = stmt.order_by(ChangeRequest.requested_at.desc())
    result = await db.execute(stmt)
    return [(request, user) for request, user in result.all()]
