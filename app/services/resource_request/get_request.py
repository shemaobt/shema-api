from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.services.resource_request._loading import Loaded, load
from app.services.resource_request._membership import is_member_of
from app.services.resource_request._scope import reach


async def get_request(db: AsyncSession, request_id: str, user: User, app_key: str) -> Loaded:
    """One request, if this caller reaches it.

    **Out of scope answers 404 and not 403**, and that is a decision rather than laziness: a
    403 would confirm that the id exists, which is the one thing a team must not learn about
    another team's request. The two cases are indistinguishable from outside on purpose.

    **A member of the request's project reaches it too**, drafts included — GATE-04 D1 and D2
    (OBT-519), built by BE-19 (OBT-520) — and the membership is read only after the roles
    said no, so the board's readers never pay for it.

    **The author short-circuits before the roles are read at all**, so reading one's own
    request costs no role query — and everyone else costs exactly one (PR #281, review).
    """
    loaded = await load(db, request_id)
    if loaded is None:
        raise NotFoundError(f"Request not found: {request_id}")

    if loaded.request.created_by != user.id:
        reaches = await reach(db, user, app_key)
        project = loaded.request.shema_project_id
        if not reaches.every and not (
            project is not None and await is_member_of(db, user.id, project)
        ):
            raise NotFoundError(f"Request not found: {request_id}")

    return loaded
