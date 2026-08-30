from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.services.resource_request._evaluation import (
    EvaluationRecord,
    latest_snapshot,
    load_evaluation,
)
from app.services.resource_request.get_request import get_request


async def get_evaluation(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> EvaluationRecord:
    """The mesa's evaluation of this request's latest snapshot, whole.

    The route in front of this gates on ``view_evaluation`` — the capability the team does
    not hold — which is §4.1's rule made real: the evaluation is its own aggregate with its
    own read permission, never a field of the request's response. What a team may read of
    it is exactly one field, and that travels through ``request_status``, not here.

    An unsubmitted request and an unevaluated snapshot both answer 404: in neither case
    does the thing being asked for exist yet, and *not started* is not a state of an
    evaluation — it is the absence of one.
    """
    loaded = await get_request(db, request_id, user, app_key)

    snapshot = await latest_snapshot(db, request_id)
    if snapshot is None:
        raise NotFoundError(f"No evaluation: request {request_id} has not been submitted.")

    record = await load_evaluation(db, snapshot.id, loaded.request.request_type.value)
    if record is None:
        raise NotFoundError(f"No evaluation yet for request {request_id}.")
    return record
