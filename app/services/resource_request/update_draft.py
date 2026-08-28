from datetime import datetime
from typing import NamedTuple

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.auth import User
from app.db.models.resource_request import RRBudgetLine, RRRequestSections
from app.models.resource_request import RequestDraftIn
from app.services.resource_request._document import split
from app.services.resource_request._loading import Loaded, load
from app.services.resource_request.get_request import get_request
from app.utils.stored_time import as_utc


class Discarded(NamedTuple):
    """What the client is told when its copy lost, and when each side was saved."""

    winner: str
    client_saved_at: datetime | None
    server_saved_at: datetime


class Saved(NamedTuple):
    loaded: Loaded
    discarded: Discarded | None


async def update_draft(
    db: AsyncSession,
    request_id: str,
    draft: RequestDraftIn,
    user: User,
    app_key: str,
    client_saved_at: datetime | None = None,
) -> Saved:
    """Rewrite a draft, resolving a two-sided edit by **latest save wins**, never by merge.

    Offline filling keeps working (RF-NF-03), so the same request can be edited in a browser
    that has been away and on the server since. Merging the two would invent a document
    neither side wrote — a paragraph half from each — which is why the issue asks for a rule
    and a warning instead.

    The rule compares **when each side was last saved**, not who spoke last:

    * no ``client_saved_at`` — the client is not tracking one, and there is nothing to
      compare. The write stands. A first sync lands here.
    * the client's save is at least as new — the write stands, silently. This is the
      ordinary case.
    * the server's row is newer — **the incoming copy is discarded** and the caller is told,
      with both timestamps. Writing it anyway would make "latest wins" a phrase with no
      consequence, and would throw away a save that happened *after* the one being sent.

    Discarding is the harsh half and it is deliberate. The alternative loses the newer work
    silently; this loses the older work loudly, and the caller has the payload it just tried
    to send, so nothing is unrecoverable on that side.

    **A ``saved_at`` with no offset is refused rather than read as UTC**, and that is the one
    place this module parts company with ``app/utils/stored_time.py``. That module normalises
    a moment the *database* wrote, where UTC is the only thing this codebase ever stores; a
    moment off the **wire** carries whatever the sender's clock had, and guessing wrong here
    does not draw a time three hours off — it decides whose work is thrown away. The stored
    side goes through ``as_utc``; the wire side has to say what it means.

    **A submitted request is not a draft.** Editing after submission would move the ground
    under an evaluation that points at a frozen snapshot; the way back in is a revision.
    """
    loaded = await get_request(db, request_id, user, app_key)

    if loaded.request.submitted_at is not None:
        raise ConflictError(
            "This request was already submitted. Editing it now would change what the mesa "
            "is evaluating; open a revision instead."
        )

    if client_saved_at is not None and client_saved_at.tzinfo is None:
        raise ValidationError(
            "saved_at needs an offset: send 2026-08-28T12:00:00Z or "
            "2026-08-28T09:00:00-03:00, not a bare local time."
        )

    server_saved_at = as_utc(loaded.request.updated_at)
    if client_saved_at is not None and client_saved_at < server_saved_at:
        return Saved(
            loaded=loaded,
            discarded=Discarded(
                winner="server",
                client_saved_at=client_saved_at,
                server_saved_at=server_saved_at,
            ),
        )

    parts = split(draft)
    for column, value in parts.spine.items():
        setattr(loaded.request, column, value)

    if loaded.sections is None:
        db.add(RRRequestSections(request_id=request_id, content=parts.sections))
    else:
        loaded.sections.content = parts.sections

    await db.execute(delete(RRBudgetLine).where(RRBudgetLine.request_id == request_id))
    for line in parts.budget:
        db.add(RRBudgetLine(request_id=request_id, **line))

    await db.commit()

    written = await load(db, request_id)
    assert written is not None
    return Saved(loaded=written, discarded=None)
