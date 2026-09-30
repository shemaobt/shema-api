"""The request lifecycle on the wire: start, draft, read, cancel, submit, revise.

Thin by the house rule and thin in fact — every handler parses, calls one service and shapes
the answer. ``NotFoundError``, ``ConflictError`` and ``ValidationError`` all have global
handlers, so nothing here maps a status code by hand.

No SQLAlchemy model is named here either — ``CLAUDE.md`` §2 keeps them out of the api layer,
and ``RequestOut.of`` is where a row becomes an envelope.

**The writes guard on ``edit_requests`` and the scope is not here.** The roles hold
``edit_requests`` (GATE-02 D4), and which instance each may write is the service's pen, not the
guard's (BE-25). The guards answer *may act on requests* and say nothing
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

**The endorsement is not a route here any more** (BE-23, OBT-535): the base leader has no
account and endorses through the link submission mails him (``endorse.py``, public). What
stays here is the Admin's resend of that link.
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from app.api.resource_requests._deps import (
    APP_KEY,
    Db,
    ReaderReadsFunds,
    RequestReader,
    TeamWriter,
    WriterReadsFunds,
)
from app.api.shema._deps import APP_KEY as SHEMA_APP_KEY
from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.resource_request import (
    DiscardedOut,
    EndorsementResentOut,
    RequestCardOut,
    RequestDraftIn,
    RequestOut,
    RequestSavedOut,
    StartIn,
    SubmissionOut,
)
from app.services import resource_request as service
from app.services.resource_request._cards import CardFacts
from app.services.resource_request._document import document
from app.services.resource_request._loading import Loaded

router = APIRouter(tags=["resource requests"])

SignedIn = Annotated[User, Depends(get_current_user)]


def _cards(facts: list[CardFacts]) -> list[RequestCardOut]:
    return [
        RequestCardOut.of(
            fact.request,
            decision=fact.decision,
            open=fact.open,
            can_edit=fact.can_edit,
            started_by_name=fact.started_by_name,
        )
        for fact in facts
    ]


def _out(loaded: Loaded, reads_funds: bool, editing: service.Edits) -> RequestOut:
    return RequestOut.of(
        loaded.request,
        document(*loaded),
        reads_funds=reads_funds,
        can_edit=editing.can_edit(loaded.request),
    )


@router.post("/requests/start", status_code=status.HTTP_201_CREATED)
async def start_request(
    start: StartIn, user: TeamWriter, db: Db, reads_funds: WriterReadsFunds
) -> RequestOut:
    """*Iniciar*: the project's instance, empty, with the caller holding the pen (BE-25).

    409 when the project already has one open — whoever started it submits or cancels first.
    """
    request = await service.start_request(db, start.request_type, user, APP_KEY, start.project_id)
    loaded = await service.request_for(db, request.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.edits_for(db, user, APP_KEY))


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_request(
    draft: RequestDraftIn,
    user: TeamWriter,
    db: Db,
    reads_funds: WriterReadsFunds,
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
    loaded = await service.request_for(db, request.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.edits_for(db, user, APP_KEY))


@router.get("/requests")
async def list_requests(
    reader: RequestReader, db: Db, reads_funds: ReaderReadsFunds
) -> list[RequestOut]:
    """The spine only — the documents are not read by a listing and are not sent to one.

    A link session reads its own link's requests (BE-26, OBT-537); an account, its scope."""
    rows = await service.requests_for(db, reader, APP_KEY)
    editing = await service.edits_for(db, reader, APP_KEY)
    return [
        RequestOut.of(row, {}, reads_funds=reads_funds, can_edit=editing.can_edit(row))
        for row in rows
    ]


@router.get("/requests/cards")
async def list_request_cards(reader: RequestReader, db: Db) -> list[RequestCardOut]:
    """The same rows as ``GET /requests``, drawn as cards (BE-24): what the tracking list
    reads, and the same projection the PME's project page reads. Declared before
    ``/requests/{request_id}`` so ``cards`` is never taken for an id."""
    return _cards(await service.cards_for(db, reader, APP_KEY))


@router.get("/projects/{project_id}/requests")
async def list_project_requests(project_id: str, user: SignedIn, db: Db) -> list[RequestCardOut]:
    """The requests of one PME project, as cards (BE-24, OBT-536).

    **A session and nothing else at the door**, and that is the one route in this module
    shaped so: the PME's regional coordinator reads this and holds no role in the form, so
    this module's gate would refuse the very reader the route exists for. Who reaches the
    project — board roles, the region, the membership — is the service's, and everyone else
    meets the Shemá module's 404.
    """
    facts = await service.list_project_requests(db, project_id, user, APP_KEY, SHEMA_APP_KEY)
    return _cards(facts)


@router.get("/requests/{request_id}")
async def read_request(
    request_id: str, reader: RequestReader, db: Db, reads_funds: ReaderReadsFunds
) -> RequestOut:
    loaded = await service.request_for(db, request_id, reader, APP_KEY)
    return _out(loaded, reads_funds, await service.edits_for(db, reader, APP_KEY))


@router.post("/requests/{request_id}/cancel")
async def cancel_request(
    request_id: str, user: TeamWriter, db: Db, reads_funds: WriterReadsFunds
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
    user: TeamWriter,
    db: Db,
    reads_funds: WriterReadsFunds,
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
    request_id: str, user: TeamWriter, db: Db, reads_funds: WriterReadsFunds
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


@router.post("/requests/{request_id}/endorsement/resend")
async def resend_endorsement(request_id: str, user: SignedIn, db: Db) -> EndorsementResentOut:
    """The Admin alone, decided in the service: a session at the door and nothing else, like
    the request links (``links.py``) — the PME's Admin may hold no role in the form."""
    resent = await service.resend_endorsement(db, request_id, user, APP_KEY, SHEMA_APP_KEY)
    return EndorsementResentOut(sent=resent.sent)


@router.post("/requests/{request_id}/revise", status_code=status.HTTP_201_CREATED)
async def revise_request(
    request_id: str, user: TeamWriter, db: Db, reads_funds: WriterReadsFunds
) -> RequestOut:
    """Answers 201 and the **new** request: a revision is a row, never an edit.

    ``TeamWriter`` since FE-55 (OBT-542): the request link that started a request reopens it
    after *revisar*, as its starter would.
    """
    revision = await service.open_revision(db, request_id, user, APP_KEY)
    loaded = await service.request_for(db, revision.id, user, APP_KEY)
    return _out(loaded, reads_funds, await service.edits_for(db, user, APP_KEY))
