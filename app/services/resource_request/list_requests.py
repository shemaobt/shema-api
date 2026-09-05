from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._scope import reach


async def list_requests(db: AsyncSession, user: User, app_key: str) -> list[RRRequest]:
    """The spine of every request this caller reaches, newest first.

    The spine and not the documents: this is what the board and the lists read, and §4.2
    made the sections their own table precisely so a listing never drags the 45 answers it
    does not show. ``ix_rr_requests_stage_created`` is the index that ordering rides on.

    The Líder's middle reach is ``_scope.py``'s decision, restated in SQL: his own rows —
    the ``equipe`` floor every account carries — plus everything submitted, and no draft
    of another team ever leaves the database for him.

    **The roles are read once and both answers come from it.** The two halves used to be
    two calls, and since ``auto_approve`` makes everyone ``equipe`` the first always said
    *narrower* and the second always ran — so every team member paid the same three-table
    join twice on every load of this list (PR #281, review).
    """
    stmt = select(RRRequest).order_by(RRRequest.created_at.desc())
    reaches = await reach(db, user, app_key)

    if not reaches.every:
        if reaches.submitted:
            stmt = stmt.where(
                or_(RRRequest.created_by == user.id, RRRequest.submitted_at.is_not(None))
            )
        else:
            stmt = stmt.where(RRRequest.created_by == user.id)

    return list((await db.execute(stmt)).scalars().all())
