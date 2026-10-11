"""The record's media — the bytes of one photo, and the coordination taking its authorization back.

OBT-578 gave the Pulso Mensal an image whose use the team authorizes; what the coordination may do
about that authorization is **take it back**, and nothing else — granting in the team's place
would be the server recording a consent nobody gave (``withdraw_image_authorization``). The route
is ``CoordinatorUser``'s for the reason every write of the record is coordination's, and the
service decides the rest, per
[ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md).

**The bytes have one door, and it is a link minted per call** (OBT-581). The record carries the
photo's ``id`` and never its address: a signed URL in a record would outlive its own fifteen
minutes in whatever holds the record, and would reach every reader the record reaches, where the
gate below refuses some of them. So ``GET …/media/{item_id}/link`` is a separate call, answered
by ``media_download_url`` behind its three gates — the caller's scope, an object to serve, and
``can_share_media`` plus the caller's **reader**: an image of a withheld project is the
coordination's until OBT-575 (Daniel, 8/oct/2026), so a reader handed the reduction is refused
with the same sentence an unauthorized item gets, and no URL is minted. The route takes the
reader to **refuse**, never to build: what it answers is an address, and the address is scoped to
the row's uuid (``docs/shema.md`` §6.4).
The screens that upload and list media stay with the console's own store until the issue that
brings them here.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import CoordinatorUser, CurrentUser, Db, Reading, Scope
from app.models.shema_privacy import ShemaAudience
from app.models.shema_record import ShemaMediaAuthorization, ShemaMediaLink
from app.services.shema import media_download_url, recorded_decision, withdraw_image_authorization

router = APIRouter()


@router.get("/projects/{project_id}/media/{item_id}/link", response_model=ShemaMediaLink)
async def read_media_link(
    project_id: str, item_id: str, user: CurrentUser, db: Db, scope: Scope, reading: Reading
) -> ShemaMediaLink:
    """A fifteen-minute signed GET for one photo's bytes — or a refusal that names no reason."""
    link = await media_download_url(
        db,
        scope,
        project_id,
        item_id,
        user=user,
        audience=ShemaAudience.COORDENACAO,
        readership=reading,
    )
    return ShemaMediaLink(url=link.url, expires_in_minutes=link.expires_in_minutes)


@router.post(
    "/projects/{project_id}/media/{item_id}/authorization/withdraw",
    response_model=ShemaMediaAuthorization,
)
async def withdraw_media_authorization(
    project_id: str, item_id: str, user: CoordinatorUser, db: Db, scope: Scope
) -> ShemaMediaAuthorization:
    """Refuse the sharing of one photo from here on, and erase it from the Pulse that brought it."""
    item = await withdraw_image_authorization(db, scope, project_id, item_id, user=user)
    decision = recorded_decision(item)
    assert decision is not None  # a withdrawal always records one
    return decision
