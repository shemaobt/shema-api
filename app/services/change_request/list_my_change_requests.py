from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.change_request import ChangeRequest


async def list_my_change_requests(
    db: AsyncSession, requester_id: str
) -> list[tuple[ChangeRequest, User]]:
    stmt = (
        select(ChangeRequest, User)
        .join(User, User.id == ChangeRequest.requester_user_id)
        .where(ChangeRequest.requester_user_id == requester_id)
        .order_by(ChangeRequest.requested_at.desc())
    )
    result = await db.execute(stmt)
    return [(request, user) for request, user in result.all()]
