"""``GET /me`` — who the signed-in account is in the form (FE-52, OBT-538).

A session and nothing else at the door, like the PME's project cards: an account with no
role and no membership is not refused here, it is **told** so — empty lists — and the form
reads that as *without a role in this app*, the sentence it already has for it.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.resource_requests._deps import APP_KEY, Db
from app.core.auth_middleware import get_current_user
from app.db.models.auth import User
from app.models.resource_request import FormIdentityOut
from app.services import resource_request as service

router = APIRouter(tags=["resource requests"])


@router.get("/me")
async def who_am_i(user: Annotated[User, Depends(get_current_user)], db: Db) -> FormIdentityOut:
    identity = await service.who_am_i(db, user, APP_KEY)
    return FormIdentityOut(roles=list(identity.roles), projects=list(identity.projects))
