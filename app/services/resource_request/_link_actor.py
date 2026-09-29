"""The link holder as a subject of this module — BE-26 (OBT-537).

Someone who entered by the Admin's request link has **no account** (GATE-04 D4): what they are
to this module is the link. ``LinkActor`` is that subject, and it reaches exactly one thing —
**the requests of its own link** — never another link's, never a project's.

It writes an instance its link started (``started_by_link_id``), which is ``can_edit``'s
answer here; the routes that write by link are PR C's.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, NotFoundError
from app.db.models.resource_request import RRRequest, RRRequestLink
from app.services.resource_request._links import link_status
from app.services.resource_request._loading import Loaded, load


@dataclass(frozen=True)
class LinkActor:
    link: RRRequestLink

    def can_edit(self, request: RRRequest) -> bool:
        open_draft = request.submitted_at is None and request.cancelled_at is None
        return open_draft and request.started_by_link_id == self.link.id


async def link_actor(db: AsyncSession, link_id: str) -> LinkActor:
    """The live link a session names, or a 401: a revoked or expired link ends its sessions."""
    link = await db.get(RRRequestLink, link_id)
    if link is None or link_status(link, datetime.now(UTC)) not in ("pending", "verified"):
        raise AuthenticationError("This request link is no longer valid.")
    return LinkActor(link=link)


async def link_requests(db: AsyncSession, actor: LinkActor) -> list[RRRequest]:
    """Every request of this link, newest first — cancelled ones out, as in ``list_requests``."""
    rows = await db.execute(
        select(RRRequest)
        .where(RRRequest.request_link_id == actor.link.id, RRRequest.cancelled_at.is_(None))
        .order_by(RRRequest.created_at.desc())
    )
    return list(rows.scalars().all())


async def get_link_request(db: AsyncSession, request_id: str, actor: LinkActor) -> Loaded:
    """One request of this link, or the same 404 ``get_request`` answers out of scope."""
    loaded = await load(db, request_id)
    if loaded is None or loaded.request.request_link_id != actor.link.id:
        raise NotFoundError(f"Request not found: {request_id}")
    return loaded
