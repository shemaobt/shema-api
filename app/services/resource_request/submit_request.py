from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest, RRSnapshot
from app.models.resource_request import RequestSubmissionIn
from app.services.resource_request._document import document
from app.services.resource_request.get_request import get_request


class Submitted(NamedTuple):
    request: RRRequest
    snapshot: RRSnapshot


async def submit_request(db: AsyncSession, request_id: str, user: User, app_key: str) -> Submitted:
    """Freeze what is stored, and stop the document moving under the mesa.

    **It takes no payload**, and that is the load-bearing choice. GATE-03 D1 answered that
    the team submits online, and the draft it submits is already here — so sending the
    content again would open the gap this issue exists to close: the snapshot would freeze
    what the last request said rather than what the team had saved, and *the mesa evaluated
    what the team submitted* would depend on the two agreeing.

    Validating storage against the stricter class is free because ``document()`` **is** the
    payload shape: what comes out of the read path goes straight into
    ``RequestSubmissionIn``. That is the second thing the one-serializer rule buys, after the
    snapshot itself.

    A Pydantic failure is re-raised as this API's ``ValidationError`` rather than escaping:
    it is not a malformed request body — the body is empty — it is a stored draft that is not
    finished, and it deserves to say so.

    Nothing here moves the card. A submitted request is in ``triagem`` because that is where
    it was created, and every stage change afterwards is BE-08's with its ledger movement
    attached.
    """
    loaded = await get_request(db, request_id, user, app_key)

    if loaded.request.submitted_at is not None:
        raise ConflictError("This request was already submitted.")

    frozen = document(*loaded)
    try:
        RequestSubmissionIn.model_validate(frozen)
    except PydanticValidationError as incomplete:
        raise ValidationError(f"This request cannot be submitted yet: {incomplete}") from None

    snapshot = RRSnapshot(request_id=request_id, document=frozen)
    db.add(snapshot)
    loaded.request.submitted_at = datetime.now(UTC)

    await db.commit()
    await db.refresh(loaded.request)
    await db.refresh(snapshot)
    return Submitted(request=loaded.request, snapshot=snapshot)
