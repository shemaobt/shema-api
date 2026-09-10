from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects._deps import assert_project_access
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.project import (
    ProjectCreate,
    ProjectLocationUpdate,
    ProjectResponse,
    ProjectUpdate,
)
from app.services import project_service

router = APIRouter()


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    language_id: str | None = Query(default=None),
    organization_id: UUID | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectResponse]:
    projects = await project_service.list_projects_for_user(
        db, user, str(organization_id) if organization_id else None, language_id
    )
    return await project_service.serialize_projects(db, projects)


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProjectResponse:
    project = await project_service.create_project(
        db,
        name=payload.name,
        language_id=payload.language_id,
        description=payload.description,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_display_name=payload.location_display_name,
        creator_user_id=str(user.id),
    )
    return await project_service.serialize_project(db, project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    project = await project_service.get_project_or_404(db, project_id)
    await assert_project_access(db, user, project_id)
    return await project_service.serialize_project(db, project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    payload: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    await assert_project_access(db, user, project_id)
    project = await project_service.update_project(
        db, project_id, **payload.model_dump(exclude_unset=True)
    )
    return await project_service.serialize_project(db, project)


@router.patch("/{project_id}/location", response_model=ProjectResponse)
async def update_project_location(
    project_id: str,
    payload: ProjectLocationUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectResponse:
    await assert_project_access(db, user, project_id)
    project = await project_service.update_project_location(
        db,
        project_id,
        latitude=payload.latitude,
        longitude=payload.longitude,
        location_display_name=payload.location_display_name,
    )
    return await project_service.serialize_project(db, project)
