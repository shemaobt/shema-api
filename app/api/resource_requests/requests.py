"""The request lifecycle on the wire: start, draft, read, cancel, submit, revise.

Thin by the house rule and thin in fact — every handler parses, calls one service and shapes
the answer. ``NotFoundError``, ``ConflictError`` and ``ValidationError`` all have global
handlers, so nothing here maps a status code by hand.

No SQLAlchemy model is named here either — ``CLAUDE.md`` §2 keeps them out of the api layer,
and ``RequestOut.of`` is where a row becomes an envelope.

**The writes guard on ``CanEditRequests``, the reads on ``CanReadRequests``, and the scope is not
here.** The three original roles hold ``edit_requests`` (GATE-02 D4), and which instance each may
write is the service's pen, not the guard's (BE-25); the Líder de Base holds only
``endorse_request`` and reads what he signs (BE-16), which is why the two GETs take the OR alias and
every route that changes a document does not. Both answer *may act on requests* and say nothing
about which ones — which rows a caller reaches is decided in
``app/services/resource_request/_scope.py``, where the reason is written: putting it in the router
would be an access rule outside the layer that owns access rules, and a listing that filtered in two
places would eventually filter differently in each.

**``ReadsFunds`` is a fact and not a door**, and it is the one thing here that varies by
caller rather than by route. ``fund_id`` on the envelope is the Painel's chip, so it is
served to ``manage_funds`` — mesa and Gestor — and is **absent** for the team, whose
envelope GATE-03 D4 keeps at *status and nothing else*. Every handler that builds an
envelope takes it and ``of()`` demands it with no default, so a route added later cannot
serve the column by forgetting to think about it.

**``can_edit`` is the other fact that varies by caller** (BE-25, OBT-534): whether this caller
writes this instance now. The reads ask ``service.editing`` once per call and hand it to
``of()``, which demands it with no default for ``reads_funds``' reason. **The three writes that
end in a known state do not ask at all**: a ``PATCH`` that got past ``require_editor`` is by
construction the pen on an open draft, so ``True``; a cancelled or submitted instance is
written by nobody, so ``False``. Asking again would read the roles a second time on the
autosave, the call a field connection pays most often (PR #572, review).

The endorsement route guards on ``CanEndorseRequest`` and takes no body: like the submit
above it, the act is the payload — who and when are stamped from the session, and a body
that could carry them would be a body that could lie about who vouched.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query, status

from app.api.resource_requests._deps import (
    APP_KEY,
    CanEditRequests,
    CanEndorseRequest,
    CanReadRequests,
    Db,
    ReadsFunds,
)
from app.models.resource_request import (
    DiscardedOut,
    RequestDraftIn,
    RequestOut,
    RequestSavedOut,
    StartIn,
    SubmissionOut,
)
from app.services import resource_request as service
from app.services.resource_request._document import document
from app.services.resource_request._loading import Loaded

router = APIRouter(tags=["resource requests"])


def _out(loaded: Loaded, reads_funds: bool, editing: service.Editing) -> RequestOut:
    return RequestOut.of(
        loaded.request,
        document(*loaded),
        reads_funds=reads_funds,
        can_edit=editing.can_edit(loaded.request),
    )


@router.post("/requests/start", status_code=status.HTTP_201_CREATED)
async def start_request(
    start: StartIn, user: CanEditRequests, db: Db, reads_funds: ReadsFunds
) -> RequestOut:
    """*Iniciar*: the project's instance, empty, with the caller holding the pen (BE-25).

    409 when the project already has one open — whoever started it submits or cancels first.
    """
    request = await service.start_request(db, start.request_type, user, APP_KEY, start.project_id)
    loaded = await service.get_request(db, request.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.editing(db, user, APP_KEY))


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_request(
    draft: RequestDraftIn,
    user: CanEditRequests,
    db: Db,
    reads_funds: ReadsFunds,
    project_id: Annotated[
        str | None,
        Query(description="The PME project the request opens from; checked against membership."),
    ] = None,
) -> RequestOut:
    """``project_id`` rides in the query, beside the document and never inside it (BE-19).

    The older door to the same act as ``/requests/start``, kept because the form creates
    through it with the document in hand; it starts the instance under the same lock.
    """
    request = await service.create_draft(db, draft, user, APP_KEY, project_id)
    loaded = await service.get_request(db, request.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.editing(db, user, APP_KEY))


@router.get("/requests")
async def list_requests(user: CanReadRequests, db: Db, reads_funds: ReadsFunds) -> list[RequestOut]:
    """The spine only — the documents are not read by a listing and are not sent to one."""
    rows = await service.list_requests(db, user, APP_KEY)
    editing = await service.editing(db, user, APP_KEY)
    return [
        RequestOut.of(row, {}, reads_funds=reads_funds, can_edit=editing.can_edit(row))
        for row in rows
    ]


@router.get("/requests/{request_id}")
async def read_request(
    request_id: str, user: CanReadRequests, db: Db, reads_funds: ReadsFunds
) -> RequestOut:
    loaded = await service.get_request(db, request_id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.editing(db, user, APP_KEY))


@router.post("/requests/{request_id}/cancel")
async def cancel_request(
    request_id: str, user: CanEditRequests, db: Db, reads_funds: ReadsFunds
) -> RequestOut:
    """No body: the starter or the Admin gives the instance up, and the project is free again.

    The row is marked, never deleted, and the answer is the request as it now stands.
    """
    loaded = await service.cancel_request(db, request_id, user, APP_KEY)
    return RequestOut.of(loaded.request, document(*loaded), reads_funds=reads_funds, can_edit=False)


@router.patch("/requests/{request_id}")
async def update_request(
    request_id: str,
    draft: RequestDraftIn,
    user: CanEditRequests,
    db: Db,
    reads_funds: ReadsFunds,
    saved_at: Annotated[
        datetime | None,
        Query(description="When the client last saved its own copy, for latest-wins."),
    ] = None,
) -> RequestSavedOut:
    """``saved_at`` rides in the query and not in the body, so the body stays the document.

    What ``GET`` returns is what this accepts, and a field about the *client's* bookkeeping
    inside it would break that — and would have to be stored or stripped, both worse.
    """
    saved = await service.update_draft(db, request_id, draft, user, APP_KEY, saved_at)
    discarded = None if saved.discarded is None else DiscardedOut(**saved.discarded._asdict())
    return RequestSavedOut.of(
        saved.loaded.request,
        document(*saved.loaded),
        reads_funds=reads_funds,
        can_edit=True,
        discarded=discarded,
    )


@router.post("/requests/{request_id}/submit")
async def submit_request(
    request_id: str, user: CanEditRequests, db: Db, reads_funds: ReadsFunds
) -> SubmissionOut:
    """No body: the draft is already here, and the snapshot freezes what was saved."""
    submitted = await service.submit_request(db, request_id, user, APP_KEY)
    return SubmissionOut.of(
        submitted.request,
        submitted.snapshot.document,
        reads_funds=reads_funds,
        can_edit=False,
        snapshot_id=submitted.snapshot.id,
    )


@router.post("/requests/{request_id}/endorse")
async def endorse_request(
    request_id: str, user: CanEndorseRequest, db: Db, reads_funds: ReadsFunds
) -> RequestOut:
    """No body: the endorsement is an act over what is stored, stamped from the session.

    No reload either: the service reads the request to check it and hands back what it
    read, unlike the two routes above, whose row is new (PR #281, review).
    """
    loaded = await service.endorse_request(db, request_id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.editing(db, user, APP_KEY))


@router.post("/requests/{request_id}/revise", status_code=status.HTTP_201_CREATED)
async def revise_request(
    request_id: str, user: CanEditRequests, db: Db, reads_funds: ReadsFunds
) -> RequestOut:
    """Answers 201 and the **new** request: a revision is a row, never an edit."""
    revision = await service.open_revision(db, request_id, user, APP_KEY)
    loaded = await service.get_request(db, revision.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.editing(db, user, APP_KEY))
