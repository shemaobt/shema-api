from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects._deps import assert_project_access
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.project import (
    ProjectGrantOrganizationAccess,
    ProjectGrantUserAccess,
    ProjectOrganizationAccessDetailResponse,
    ProjectOrganizationAccessResponse,
    ProjectUserAccessDetailResponse,
    ProjectUserAccessResponse,
    ProjectUserAccessRoleUpdate,
)
from app.services import project_service

router = APIRouter()


@router.post(
    "/{project_id}/access/users",
    response_model=ProjectUserAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_user_access(
    project_id: str,
    payload: ProjectGrantUserAccess,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectUserAccessResponse:
    await assert_project_access(db, actor, project_id)
    await project_service.get_project_or_404(db, project_id)
    access = await project_service.grant_user_access(db, project_id, payload.user_id, payload.role)
    return ProjectUserAccessResponse.model_validate(access)


@router.post(
    "/{project_id}/access/organizations",
    response_model=ProjectOrganizationAccessResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_organization_access(
    project_id: str,
    payload: ProjectGrantOrganizationAccess,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectOrganizationAccessResponse:
    await assert_project_access(db, actor, project_id)
    await project_service.get_project_or_404(db, project_id)
    access = await project_service.grant_organization_access(
        db, project_id, payload.organization_id
    )
    return ProjectOrganizationAccessResponse.model_validate(access)


@router.get(
    "/{project_id}/access/users",
    response_model=list[ProjectUserAccessDetailResponse],
)
async def list_user_access(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectUserAccessDetailResponse]:
    await assert_project_access(db, actor, project_id)
    await project_service.get_project_or_404(db, project_id)
    rows = await project_service.list_project_user_access(db, project_id)
    return [
        ProjectUserAccessDetailResponse(
            id=access.id,
            project_id=access.project_id,
            user_id=access.user_id,
            email=user.email,
            display_name=user.display_name,
            avatar_url=user.avatar_url,
            role=access.role,
            granted_at=access.granted_at,
        )
        for access, user in rows
    ]


@router.get(
    "/{project_id}/access/organizations",
    response_model=list[ProjectOrganizationAccessDetailResponse],
)
async def list_organization_access(
    project_id: str,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectOrganizationAccessDetailResponse]:
    await assert_project_access(db, actor, project_id)
    await project_service.get_project_or_404(db, project_id)
    rows = await project_service.list_project_organization_access(db, project_id)
    return [
        ProjectOrganizationAccessDetailResponse(
            id=access.id,
            project_id=access.project_id,
            organization_id=access.organization_id,
            name=org.name,
            slug=org.slug,
            granted_at=access.granted_at,
        )
        for access, org in rows
    ]


@router.patch(
    "/{project_id}/access/users/{user_id}",
    response_model=ProjectUserAccessResponse,
)
async def update_user_access_role(
    project_id: str,
    user_id: str,
    payload: ProjectUserAccessRoleUpdate,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectUserAccessResponse:
    await assert_project_access(db, actor, project_id)
    access = await project_service.update_user_access_role(db, project_id, user_id, payload.role)
    return ProjectUserAccessResponse.model_validate(access)


@router.delete(
    "/{project_id}/access/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_user_access(
    project_id: str,
    user_id: str,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assert_project_access(db, actor, project_id)
    await project_service.revoke_user_access(db, project_id, user_id)


@router.delete(
    "/{project_id}/access/organizations/{organization_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def revoke_organization_access(
    project_id: str,
    organization_id: str,
    actor: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assert_project_access(db, actor, project_id)
    await project_service.revoke_organization_access(db, project_id, organization_id)
