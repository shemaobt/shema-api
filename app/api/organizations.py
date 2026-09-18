from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.core.exceptions import AuthorizationError, NotFoundError
from app.core.org_scope import get_managed_org_ids, get_managed_project_ids
from app.db.models.auth import User
from app.models.org import (
    OrganizationCreate,
    OrganizationMemberAdd,
    OrganizationMemberDetailResponse,
    OrganizationMemberResponse,
    OrganizationMemberRoleUpdate,
    OrganizationResponse,
    OrganizationStatsResponse,
    OrganizationUpdate,
)
from app.services import organization_service

router = APIRouter()


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[OrganizationResponse]:
    if user.is_platform_admin:
        orgs = await organization_service.list_organizations(db)
    else:
        managed_project_ids = await get_managed_project_ids(db, user.id)
        orgs = await organization_service.list_organizations_by_projects(db, managed_project_ids)
    return [OrganizationResponse.model_validate(o) for o in orgs]


@router.post("", response_model=OrganizationResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: OrganizationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OrganizationResponse:
    org = await organization_service.create_organization(
        db,
        payload.name,
        payload.slug,
        description=payload.description,
        logo_url=payload.logo_url,
        manager_id=payload.manager_id,
    )
    return OrganizationResponse.model_validate(org)


@router.get("/slug/{slug}", response_model=OrganizationResponse)
async def get_organization_by_slug(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OrganizationResponse:
    org = await organization_service.get_organization_by_slug(db, slug)
    if not org:
        raise NotFoundError("Organization not found")
    return OrganizationResponse.model_validate(org)


@router.get("/{org_id}/stats", response_model=OrganizationStatsResponse)
async def get_organization_stats(
    org_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OrganizationStatsResponse:
    await organization_service.get_organization_or_404(db, org_id)
    if not user.is_platform_admin:
        managed = await get_managed_org_ids(db, user.id)
        if org_id not in managed:
            raise AuthorizationError("You do not have access to this organization's stats")
    return await organization_service.get_organization_stats(db, org_id)


@router.get("/{organization_id}", response_model=OrganizationResponse)
async def get_organization_by_id(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OrganizationResponse:
    org = await organization_service.get_organization_or_404(db, organization_id)
    return OrganizationResponse.model_validate(org)


@router.patch("/{organization_id}", response_model=OrganizationResponse)
async def update_organization(
    organization_id: str,
    payload: OrganizationUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OrganizationResponse:
    org = await organization_service.update_organization(
        db,
        organization_id,
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        logo_url=payload.logo_url,
        manager_id=payload.manager_id,
    )
    return OrganizationResponse.model_validate(org)


@router.post(
    "/{organization_id}/members",
    response_model=OrganizationMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_organization_member(
    organization_id: str,
    payload: OrganizationMemberAdd,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> OrganizationMemberResponse:
    await organization_service.get_organization_or_404(db, organization_id)
    member = await organization_service.add_member(
        db, organization_id, payload.user_id, payload.role
    )
    return OrganizationMemberResponse.model_validate(member)


@router.get(
    "/{organization_id}/members",
    response_model=list[OrganizationMemberDetailResponse],
)
async def list_organization_members(
    organization_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[OrganizationMemberDetailResponse]:
    await organization_service.get_organization_or_404(db, organization_id)
    rows = await organization_service.list_members(db, organization_id)
    return [
        OrganizationMemberDetailResponse(
            id=member.id,
            user_id=member.user_id,
            organization_id=member.organization_id,
            role=member.role,
            joined_at=member.joined_at,
            email=user.email,
            display_name=user.display_name,
        )
        for member, user in rows
    ]


@router.delete(
    "/{organization_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_organization_member(
    organization_id: str,
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> None:
    await organization_service.get_organization_or_404(db, organization_id)
    await organization_service.remove_member(db, organization_id, user_id)


@router.patch(
    "/{organization_id}/members/{user_id}",
    response_model=OrganizationMemberResponse,
)
async def update_member_role(
    organization_id: str,
    user_id: str,
    payload: OrganizationMemberRoleUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> OrganizationMemberResponse:
    await organization_service.get_organization_or_404(db, organization_id)
    member = await organization_service.update_member_role(
        db, organization_id, user_id, payload.role
    )
    return OrganizationMemberResponse.model_validate(member)
