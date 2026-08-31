from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest, RRSnapshot
from app.models.resource_request import RequestSubmissionIn
from app.services.resource_request._document import document
from app.services.resource_request._notices import post
from app.services.resource_request.get_request import get_request
from app.services.resource_request.notify_arrival import notify_arrival


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

    **This is where the electronic acceptance is recorded, and it needs no field.** Asked
    what replaces the Ponto focal's handwritten signature, the client answered *"aceite
    eletrônico"* (28/aug/2026), and what stands in its place is the act itself:
    ``created_by`` says who, ``submitted_at`` says when, both stamped by the server and
    neither typable through a payload — this route takes none. No column and no field were
    added, because the acceptance was already the shape this endpoint had. What the answer
    does move is outside this function: ``tpp_date`` is due to stop being required at
    submission — ``_ALWAYS_REQUIRED`` in ``resource_request_vocabularies.py`` still carries
    it, and that list is BE-05's — and the printed signature line goes from the form
    (frontend).

    **There is no window, no deadline and no cycle lock, and the absence is written rather
    than left to be noticed.** Asked whether submission is open all year, the client answered
    *"não por enquanto"*: nothing here compares a date with a calendar, and that is the rule
    and not an omission. The day a window exists it is a refusal **inside this function**,
    before the snapshot is written — never a filter on the read path, which would hide a
    request that was legitimately submitted. Only that half was answered; whether there is a
    paper archive to migrate is still open and was never this function's.

    Nothing here moves the card. A submitted request is in ``triagem`` because that is where
    it was created, and every stage change afterwards is BE-08's with its ledger movement
    attached.

    **This is also where the mesa and the Gestores are told** (GATE-03 D6, BE-13): the
    in-app notices are staged inside this function's transaction and the letters leave
    after its commit, so a submission that failed announces nothing and a provider outage
    cannot un-submit anything. Arrival is announced once, here — a draft still being typed
    announces nothing, and a card dragged later announces nothing either.
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

    letters = await notify_arrival(db, request=loaded.request, actor_id=user.id, app_key=app_key)

    await db.commit()
    await db.refresh(loaded.request)
    await db.refresh(snapshot)

    await post(letters)
    return Submitted(request=loaded.request, snapshot=snapshot)
