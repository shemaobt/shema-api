"""The field-by-field trail on the wire (BE-15, OBT-475).

One route, read-only: the trail is written by the writes themselves — ``update_draft``
hangs it on every save that stands — and rows that could be posted or edited here would
be exactly the trail ``rr_request_field_history``'s append-only trigger exists to refuse.

**Who reads it is decided in the service and recorded there** — the short form: whoever
reaches the request reaches its trail, through the same ``get_request`` scope and the
same 404 for everyone else. The guard is ``CanEditRequests`` like every other
request-lifecycle route, because the trail carries only request fields, which every
holder of that capability may already read in their current values. The avaliação's
trail is not served here: it carries scores and a decision — ``view_evaluation``
content — and its surface arrives with BE-06's evaluation endpoints.
"""

from fastapi import APIRouter

from app.api.resource_requests._deps import APP_KEY, CanEditRequests, Db
from app.models.resource_request import FieldChangeOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])


@router.get("/requests/{request_id}/history")
async def read_request_history(
    request_id: str, user: CanEditRequests, db: Db
) -> list[FieldChangeOut]:
    """Every recorded change of this request's fields, oldest first."""
    rows = await service.list_request_history(db, request_id, user, APP_KEY)
    return [FieldChangeOut.of(row) for row in rows]
