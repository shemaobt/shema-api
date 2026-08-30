"""The privileged-access surface: naming, link invites, and the revocation list.

Every route is thin — the asymmetric gate (Admin and Gestor concede, Admin
revokes), the mesa/gestor exclusivity and the self-grant refusals all live in
``app/services/resource_request_access``; the global exception handlers turn
their refusals into status codes. The one route with no auth dependency is the
invite lookup: an anonymous link-holder must be answerable before they have an
account, which is the point of the link.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.resource_requests._deps import APP_KEY
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.resource_request_access import (
    AccessGrantRequest,
    AccessGrantResponse,
    AccessOverviewResponse,
    AccessRevokeRequest,
    InviteCreatedResponse,
    InviteCreateRequest,
    InviteDescriptionResponse,
    InviteResponse,
    InviteRevokeRequest,
)
from app.services import resource_request_access as access_service

router = APIRouter()


@router.get("", response_model=AccessOverviewResponse)
async def overview(
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AccessOverviewResponse:
    return await access_service.list_access(db, actor, APP_KEY)


@router.post("/grants", response_model=AccessGrantResponse)
async def grant(
    payload: AccessGrantRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AccessGrantResponse:
    assignment = await access_service.grant_access(
        db, actor, payload.target_user_id, APP_KEY, payload.role_key
    )
    return AccessGrantResponse(
        user_id=assignment.user_id,
        role_key=payload.role_key,
        granted_at=assignment.granted_at,
        granted_by=assignment.granted_by,
        revoked_at=assignment.revoked_at,
        revoked_by=assignment.revoked_by,
    )


@router.post("/grants/revoke", response_model=AccessGrantResponse)
async def revoke(
    payload: AccessRevokeRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AccessGrantResponse:
    assignment = await access_service.revoke_access(
        db, actor, payload.target_user_id, APP_KEY, payload.role_key
    )
    return AccessGrantResponse(
        user_id=assignment.user_id,
        role_key=payload.role_key,
        granted_at=assignment.granted_at,
        granted_by=assignment.granted_by,
        revoked_at=assignment.revoked_at,
        revoked_by=assignment.revoked_by,
    )


@router.post("/invites", response_model=InviteCreatedResponse, status_code=201)
async def create_invite(
    payload: InviteCreateRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> InviteCreatedResponse:
    return await access_service.create_invite(db, actor, APP_KEY, payload.email, payload.role_key)


@router.post("/invites/revoke", response_model=InviteResponse)
async def revoke_invite(
    payload: InviteRevokeRequest,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> InviteResponse:
    return await access_service.revoke_invite(db, actor, payload.invite_id)


@router.get("/invites/{token}", response_model=InviteDescriptionResponse)
async def describe_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> InviteDescriptionResponse:
    return await access_service.describe_invite(db, token)


@router.post("/invites/{token}/accept", response_model=AccessGrantResponse)
async def accept_invite(
    token: str,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(get_current_user),
) -> AccessGrantResponse:
    return await access_service.accept_invite(db, actor, token)
