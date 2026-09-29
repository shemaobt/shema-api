"""Who writes a request: a person, or the request link that started it (BE-26, OBT-537).

``_editing.py`` answers for a person — the starter or the Admin (BE-25). A link's holder has
no account, and the rule is the same one read for them: **the link that started the instance
writes it**, and nothing else does on the link's side. A link writes its own instance and
never another link's or a project's; a cancelled instance takes no write from anyone.

``reach_for_writing`` is the door the **draft's** writes go through — saving and cancelling —
so the read scope and the pen are checked together and in that order: out of reach is 404
before *not yours* is 403, the order ``get_request`` and ``require_editor`` already keep.

**Submitting is deliberately not one of them.** It is the electronic acceptance, and only the
starter signs — the person in ``started_by`` or the link in ``started_by_link_id`` — so the
Admin that ``require_editor`` admits must not pass there. ``submit_request`` reads through
``request_for`` and checks the signer itself (BE-18). A new write route decides which of the
two it is before it picks a door.
"""

from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError
from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._editing import require_editor
from app.services.resource_request._link_actor import LinkActor
from app.services.resource_request._loading import Loaded
from app.services.resource_request.read_as import request_for

Writer = User | LinkActor


class TrailAuthor(TypedDict):
    changed_by: str | None
    changed_by_link_id: str | None


def trail_author(writer: Writer) -> TrailAuthor:
    """The trail's author for ``writer`` — never the Admin who issued a link (BE-26)."""
    if isinstance(writer, LinkActor):
        return {"changed_by": None, "changed_by_link_id": writer.link.id}
    return {"changed_by": writer.id, "changed_by_link_id": None}


async def require_writer(
    db: AsyncSession, request: RRRequest, writer: Writer, app_key: str
) -> None:
    if isinstance(writer, LinkActor):
        if request.started_by_link_id != writer.link.id:
            raise AuthorizationError("Only the link that started this request writes it.")
        if request.cancelled_at is not None:
            raise ConflictError("This request was cancelled; start a new one instead.")
        return
    await require_editor(db, request, writer, app_key)


async def reach_for_writing(
    db: AsyncSession, request_id: str, writer: Writer, app_key: str
) -> Loaded:
    loaded = await request_for(db, request_id, writer, app_key)
    await require_writer(db, loaded.request, writer, app_key)
    return loaded
