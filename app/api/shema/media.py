"""The record's media — one route today: the coordination withdrawing a photo's authorization.

OBT-578 gave the Pulso Mensal an image whose use the team authorizes; what the coordination may do
about that authorization is **take it back**, and nothing else — granting in the team's place
would be the server recording a consent nobody gave (``withdraw_image_authorization``). The route
is ``CoordinatorUser``'s for the reason every write of the record is coordination's, and the
service decides the rest, per
[ADR 0009](../../../docs/adr/0009-routers-never-touch-the-database.md).
The screens that upload and list media stay with the console's own store until the issue that
brings them here; this file holds the one write the archive's erasure needs.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.shema._deps import CoordinatorUser, Db, Scope
from app.models.shema_record import ShemaMediaAuthorization
from app.services.shema import recorded_decision, withdraw_image_authorization

router = APIRouter()


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
