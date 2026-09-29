"""The Admin's request links — issue, list, revoke (BE-26, OBT-537).

A session and nothing else at the door, and the service decides: the Admin holds ``admin`` in
either app (``_links.require_link_admin``), and the PME's dialog (OBT-544) calls these routes
for an Admin who may hold no role in the form at all — the module's own gate would refuse them.
"""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.resource_requests._deps import APP_KEY, Db
from app.api.shema._deps import APP_KEY as SHEMA_APP_KEY
from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.resource_request import IssuedRequestLinkOut, RequestLinkIn, RequestLinkOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])

SignedIn = Annotated[User, Depends(get_current_user)]


@router.post("/links", status_code=status.HTTP_201_CREATED)
async def issue_request_link(link: RequestLinkIn, user: SignedIn, db: Db) -> IssuedRequestLinkOut:
    """The token and the code travel in this answer and in no other."""
    issued = await service.create_request_link(
        db, str(link.email), link.project_hint, user, APP_KEY, SHEMA_APP_KEY
    )
    now = datetime.now(UTC)
    return IssuedRequestLinkOut.of(
        issued.link,
        service.link_status(issued.link, now),
        token=issued.token,
        code=issued.code,
    )


@router.get("/links")
async def list_request_links(user: SignedIn, db: Db) -> list[RequestLinkOut]:
    links = await service.list_request_links(db, user, APP_KEY, SHEMA_APP_KEY)
    now = datetime.now(UTC)
    return [RequestLinkOut.of(link, service.link_status(link, now)) for link in links]


@router.post("/links/{link_id}/revoke")
async def revoke_request_link(link_id: str, user: SignedIn, db: Db) -> RequestLinkOut:
    link = await service.revoke_request_link(db, link_id, user, APP_KEY, SHEMA_APP_KEY)
    return RequestLinkOut.of(link, service.link_status(link, datetime.now(UTC)))
