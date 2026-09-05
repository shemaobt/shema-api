from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.services.resource_request._loading import Loaded, load
from app.services.resource_request._scope import reach


async def get_request(db: AsyncSession, request_id: str, user: User, app_key: str) -> Loaded:
    """One request, if this caller reaches it.

    **Out of scope answers 404 and not 403**, and that is a decision rather than laziness: a
    403 would confirm that the id exists, which is the one thing a team must not learn about
    another team's request. The two cases are indistinguishable from outside on purpose —
    and another team's *draft* answers the Líder the same 404 for the same reason: his reach
    starts where a document is submitted (``_scope.py``), and before that the draft does not
    exist for him.

    **The author short-circuits before the roles are read at all**, so reading one's own
    request costs no role query — and everyone else costs exactly one, because ``reach``
    answers both halves from a single read (PR #281, review).
    """
    loaded = await load(db, request_id)
    if loaded is None:
        raise NotFoundError(f"Request not found: {request_id}")

    if loaded.request.created_by != user.id:
        reaches = await reach(db, user, app_key)
        submitted = loaded.request.submitted_at is not None
        if not reaches.every and not (submitted and reaches.submitted):
            raise NotFoundError(f"Request not found: {request_id}")

    return loaded
