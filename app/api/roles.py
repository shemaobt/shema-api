from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.role import (
    RoleAssignmentResponse,
    RoleAssignRequest,
    RoleCheckResponse,
    RoleRevokeRequest,
)
from app.services import authorization_service

router = APIRouter()


@router.post("/assign", response_model=RoleAssignmentResponse)
async def assign_role(
    payload: RoleAssignRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> RoleAssignmentResponse:
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
