from datetime import UTC, datetime
from typing import NamedTuple

from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError, IncompleteSubmission
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

    A Pydantic failure is re-raised as ``IncompleteSubmission`` rather than escaping:
    it is not a malformed request body — the body is empty — it is a stored draft that is not
    finished, and it deserves to say so.

    **This is where the electronic acceptance is recorded, and it needs no field.** Asked
    what replaces the Ponto focal's handwritten signature, the client answered *"aceite
    eletrônico"* (28/aug/2026), and what stands in its place is the act itself:
    ``created_by`` says who, ``submitted_at`` says when, both stamped by the server and
    neither typable through a payload — this route takes none. No column and no field were
    added, because the acceptance was already the shape this endpoint had.

    **Because submitting is signing, only the author submits — and that refusal lives
    here, not in the router's guard.** ``CanEditRequests`` is held by all three roles
    (GATE-02 D4), and ``_scope.py`` lets the mesa and the Gestor reach every draft — they
    keep reading, and since BE-25 writing a draft is its starter's (``_editing.py``). What
    they may not do is press a button that signs in ``created_by``'s name, so the check
    compares the caller to the author rather than asking what the caller may do. It binds
    the platform admin too, deliberately, where every guard in ``_deps.py`` waves them
    through: those answer *may act here*, an installation rule; this one answers *whose
    name goes on the acceptance*, which no grant can transfer. The message says the real
    reason — not *no permission* but *only the person who filled it signs*.

    **The author it compares against is ``started_by``, not ``created_by``** (BE-25, OBT-534):
    the two agree for every request a person opens, and stop agreeing the day a link opens
    one (BE-26), so the acceptance is compared with the column that says who holds the pen.
    The Admin who started an instance for a team is its starter, and submits it; the Admin
    who did not, does not — which is the same no-grant-transfers-a-signature rule above.

    The signature lines the paper form carried follow from the same answer, in
    ``resource_request_vocabularies.py`` (OBT-483): ``tpp_date``, ``leader_name`` and
    ``leader_date`` are out of ``_ALWAYS_REQUIRED`` — the acceptance replaces them —
    while ``tpp_name`` stays required, because it is the requester the mesa reads on the
    card and the account submitting may not be the Ponto focal.

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

    if loaded.request.started_by != user.id:
        raise AuthorizationError(
            "Submitting is the electronic acceptance, and only whoever started this "
            "request signs it. Reading stays open to the team; signing in the starter's "
            "name does not."
        )

    if loaded.request.cancelled_at is not None:
        raise ConflictError("This request was cancelled; start a new one instead.")

    if loaded.request.submitted_at is not None:
        raise ConflictError("This request was already submitted.")

    frozen = document(*loaded)
    try:
        RequestSubmissionIn.model_validate(frozen)
    except PydanticValidationError as incomplete:
        # `include_input=False` is the flag that matters: without it every error carries a
        # truncated dump of the stored document, which is what made the sentence
        # unparseable and made the frontend's key scan invent faults. The other two only
        # drop noise a client has no use for — a docs URL and Pydantic's own context.
        located = incomplete.errors(include_url=False, include_context=False, include_input=False)
        raise IncompleteSubmission(
            "This request cannot be submitted yet: "
            + "; ".join(
                f"{'.'.join(str(part) for part in error['loc'])}: {error['msg']}"
                for error in located
            ),
            [{"loc": list(error["loc"]), "msg": error["msg"]} for error in located],
        ) from None

    snapshot = RRSnapshot(request_id=request_id, document=frozen)
    db.add(snapshot)
    loaded.request.submitted_at = datetime.now(UTC)

    letters = await notify_arrival(db, request=loaded.request, actor_id=user.id, app_key=app_key)

    await db.commit()
    await db.refresh(loaded.request)
    await db.refresh(snapshot)

    await post(letters)
    return Submitted(request=loaded.request, snapshot=snapshot)
