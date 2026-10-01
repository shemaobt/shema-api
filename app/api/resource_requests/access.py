"""The invite doors the PME's ``/convite`` page calls — what is left of the access surface.

FE-56 (OBT-549, 30/sep/2026) retired the form's access screen and its five doors — the
overview, naming, revoking, issuing and withdrawing an invite: roles are granted in the PME
now, by the Admin alone (OBT-522), through ``/api/shema/access``. These two stay because the
PME's ``/convite`` page still reads and accepts an invite here; moving them into the Shemá
module is a follow-up, named on the PR.

The invite lookup has no auth dependency: an anonymous link-holder must be answerable before
they have an account, which is the point of the link.
"""

from fastapi import APIRouter, Depends

from app.api.resource_requests._deps import Db
from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.resource_request_access import AccessGrantResponse, InviteDescriptionResponse
from app.services import resource_request_access as access_service

router = APIRouter()


@router.get("/invites/{token}", response_model=InviteDescriptionResponse)
async def describe_invite(
    token: str,
    db: Db,
) -> InviteDescriptionResponse:
    return await access_service.describe_invite(db, token)


@router.post("/invites/{token}/accept", response_model=AccessGrantResponse)
async def accept_invite(
    token: str,
    db: Db,
    actor: User = Depends(get_current_user),
) -> AccessGrantResponse:
    return await access_service.accept_invite(db, actor, token)
