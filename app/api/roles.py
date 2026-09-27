from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.models.role import (
    RoleAssignmentResponse,
    RoleAssignRequest,
    RoleCheckResponse,
    RoleRevokeRequest,
)
from app.services import authorization_service

router = APIRouter()

#: The two applications whose roles are granted through the PME's access surface,
#: ``/api/shema/access`` (OBT-543), and not through the two raw routes below. Written here and
#: held to ``app/api/shema/_deps.py``'s ``APP_KEY`` and ``FORM_APP_KEY`` by a test, rather than
#: imported from a module this router has no other reason to load.
PME_APP_KEYS = frozenset({"shema", "resource-request-form"})


def _refuse_the_pme_apps(actor: User, app_key: str) -> None:
    """Refuse a raw grant or revocation in the two PME apps to anyone but an installation admin.

    The surface applies what these routes cannot: the Admin never grants to themselves, mesa
    and Gestor never share an account, ``admin`` is written in both apps, a regional role
    comes with its regions and takes them away with it. Every holder of an app's ``admin``
    passes ``assert_can_manage_roles`` here, so without this line each Admin that surface
    names could step around all of it in one request. The installation admin keeps the raw
    tool, as for every other application.
    """
    if app_key in PME_APP_KEYS and not actor.is_platform_admin:
        raise AuthorizationError(
            f"Roles of '{app_key}' are granted and revoked through /api/shema/access."
        )


@router.post("/assign", response_model=RoleAssignmentResponse)
async def assign_role(
    payload: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> RoleAssignmentResponse:
    _refuse_the_pme_apps(actor, payload.app_key)
    assignment = await authorization_service.assign_role(
        db,
        actor,
        payload.target_user_id,
        payload.app_key,
        payload.role_key,
    )
    return RoleAssignmentResponse(
        user_id=assignment.user_id,
        app_key=payload.app_key,
        role_key=payload.role_key,
        granted_at=assignment.granted_at,
        revoked_at=assignment.revoked_at,
    )


@router.post("/revoke", response_model=RoleAssignmentResponse)
async def revoke_role(
    payload: RoleRevokeRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> RoleAssignmentResponse:
    _refuse_the_pme_apps(actor, payload.app_key)
    assignment = await authorization_service.revoke_role(
        db,
        actor,
        payload.target_user_id,
        payload.app_key,
        payload.role_key,
    )
    return RoleAssignmentResponse(
        user_id=assignment.user_id,
        app_key=payload.app_key,
        role_key=payload.role_key,
        granted_at=assignment.granted_at,
        revoked_at=assignment.revoked_at,
    )


@router.get("/check", response_model=RoleCheckResponse)
async def check_role(
    user_id: str = Query(...),
    app_key: str = Query(...),
    role_key: str = Query(...),
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> RoleCheckResponse:
    # A caller may always check their own roles. Probing anyone else's requires the
    # same authority as granting them (platform admin, or the app's own admin), so
    # this endpoint cannot be used as a role-membership oracle against other users.
    if user_id != actor.id:
        await authorization_service.assert_can_manage_roles(db, actor, app_key)
    allowed = await authorization_service.has_role(db, user_id, app_key, role_key)
    return RoleCheckResponse(allowed=allowed)
