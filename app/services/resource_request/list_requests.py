from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._membership import member_project_ids
from app.services.resource_request._scope import reach


async def list_requests(db: AsyncSession, user: User, app_key: str) -> list[RRRequest]:
    """The spine of every request this caller reaches, newest first.

    The spine and not the documents: this is what the board and the lists read, and §4.2
    made the sections their own table precisely so a listing never drags the 45 answers it
    does not show. ``ix_rr_requests_stage_created`` is the index that ordering rides on.

    The team's reach is its own rows **and its projects' rows**, drafts included (GATE-04 D1
    and D2, BE-19): a member reads what a teammate started. The base leader has no reach here
    since BE-23 (OBT-535) — no account, one request, through the link's public door.

    **A cancelled instance is not listed, for anyone** (BE-25, OBT-534). It was given up and
    nobody may type into it; listing it would put a dead draft beside the one the project
    actually has open. The row is still read by id (``get_request``) — it is history.
    """
    stmt = (
        select(RRRequest)
        .where(RRRequest.cancelled_at.is_(None))
        .order_by(RRRequest.created_at.desc())
    )
    reaches = await reach(db, user, app_key)

    if not reaches.every:
        own = or_(
            RRRequest.created_by == user.id,
            RRRequest.shema_project_id.in_(member_project_ids(user.id)),
        )
        stmt = stmt.where(own)

    return list((await db.execute(stmt)).scalars().all())
