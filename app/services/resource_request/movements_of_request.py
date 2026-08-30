from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.resource_request import RRFundMovement, RRRequest


async def movements_of_request(db: AsyncSession, request_id: str) -> list[RRFundMovement]:
    """Every movement a request caused, oldest first, whichever fund it touched.

    The other axis of ``movements_of_fund``, split per the house's
    ``list_project_organization_access`` / ``list_project_user_access`` shape; the 404,
    the ordering and the absence of row scoping carry the reasons written there.
    """
    request = (
        await db.execute(select(RRRequest.id).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request is None:
        raise NotFoundError(f"Request not found: {request_id}")

    return list(
        (
            await db.execute(
                select(RRFundMovement)
                .where(RRFundMovement.request_id == request_id)
                .order_by(RRFundMovement.created_at, RRFundMovement.id)
            )
        )
        .scalars()
        .all()
    )
