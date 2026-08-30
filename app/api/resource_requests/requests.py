"""The request lifecycle on the wire: draft, read, submit, revise.

Thin by the house rule and thin in fact — every handler parses, calls one service and shapes
the answer. ``NotFoundError``, ``ConflictError`` and ``ValidationError`` all have global
handlers, so nothing here maps a status code by hand.

No SQLAlchemy model is named here either — ``CLAUDE.md`` §2 keeps them out of the api layer,
and ``RequestOut.of`` is where a row becomes an envelope.

**The writes guard on ``CanEditRequests``, the reads on ``CanReadRequests``, and the scope
is not here.** The three original roles hold ``edit_requests`` (GATE-02 D4: the mesa may
edit what the team wrote); the Líder de Base holds only ``endorse_request`` and reads what
he signs (BE-16), which is why the two GETs take the OR alias and every route that changes
a document does not. Both answer *may act on requests* and say nothing about which ones —
which rows a caller reaches is decided in ``app/services/resource_request/_scope.py``,
where the reason is written: putting it in the router would be an access rule outside the
layer that owns access rules, and a listing that filtered in two places would eventually
filter differently in each.

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
)
from app.models.resource_request import (
    DiscardedOut,
    RequestDraftIn,
    RequestOut,
    RequestSavedOut,
    SubmissionOut,
)
from app.services import resource_request as service
from app.services.resource_request._document import document
from app.services.resource_request._loading import Loaded

router = APIRouter(tags=["resource requests"])


def _out(loaded: Loaded) -> RequestOut:
    return RequestOut.of(loaded.request, document(*loaded))


@router.post("/requests", status_code=status.HTTP_201_CREATED)
async def create_request(draft: RequestDraftIn, user: CanEditRequests, db: Db) -> RequestOut:
    request = await service.create_draft(db, draft, author_id=user.id)
    loaded = await service.get_request(db, request.id, user, APP_KEY)
    return _out(loaded)


@router.get("/requests")
async def list_requests(user: CanReadRequests, db: Db) -> list[RequestOut]:
    """The spine only — the documents are not read by a listing and are not sent to one."""
    rows = await service.list_requests(db, user, APP_KEY)
    return [RequestOut.of(row, {}) for row in rows]


@router.get("/requests/{request_id}")
async def read_request(request_id: str, user: CanReadRequests, db: Db) -> RequestOut:
    return _out(await service.get_request(db, request_id, user, APP_KEY))


@router.patch("/requests/{request_id}")
async def update_request(
    request_id: str,
    draft: RequestDraftIn,
    user: CanEditRequests,
    db: Db,
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
    return RequestSavedOut.of(saved.loaded.request, document(*saved.loaded), discarded=discarded)


@router.post("/requests/{request_id}/submit")
async def submit_request(request_id: str, user: CanEditRequests, db: Db) -> SubmissionOut:
    """No body: the draft is already here, and the snapshot freezes what was saved."""
    submitted = await service.submit_request(db, request_id, user, APP_KEY)
    return SubmissionOut.of(
        submitted.request, submitted.snapshot.document, snapshot_id=submitted.snapshot.id
    )


@router.post("/requests/{request_id}/endorse")
async def endorse_request(request_id: str, user: CanEndorseRequest, db: Db) -> RequestOut:
    """No body: the endorsement is an act over what is stored, stamped from the session."""
    endorsed = await service.endorse_request(db, request_id, user, APP_KEY)
    return _out(await service.get_request(db, endorsed.id, user, APP_KEY))


@router.post("/requests/{request_id}/revise", status_code=status.HTTP_201_CREATED)
async def revise_request(request_id: str, user: CanEditRequests, db: Db) -> RequestOut:
    """Answers 201 and the **new** request: a revision is a row, never an edit."""
    revision = await service.open_revision(db, request_id, user, APP_KEY)
    return _out(await service.get_request(db, revision.id, user, APP_KEY))
