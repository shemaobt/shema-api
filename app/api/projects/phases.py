from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects._deps import assert_project_access
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.phase import (
    AttachPhaseRequest,
    ProjectPhaseResponse,
    ProjectPhaseStatusUpdate,
    ProjectPhasesWithDepsResponse,
)
from app.services import phase_service

router = APIRouter()


@router.get("/{project_id}/phases-with-deps", response_model=ProjectPhasesWithDepsResponse)
async def list_project_phases_with_deps(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPhasesWithDepsResponse:
    await assert_project_access(db, user, project_id)
    return await phase_service.list_project_phases_with_deps(db, project_id)


@router.get("/{project_id}/phases", response_model=list[ProjectPhaseResponse])
async def list_project_phases(
    project_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ProjectPhaseResponse]:
    await assert_project_access(db, user, project_id)
    return await phase_service.list_project_phases_with_details(db, project_id)


@router.post(
    "/{project_id}/phases",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def attach_phase_to_project(
    project_id: str,
    payload: AttachPhaseRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assert_project_access(db, user, project_id)
    await phase_service.attach_phase_to_project(db, project_id, payload.phase_id)


@router.delete("/{project_id}/phases/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_phase_from_project(
    project_id: str,
    phase_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    await assert_project_access(db, user, project_id)
    await phase_service.detach_phase_from_project(db, project_id, phase_id)


@router.patch("/{project_id}/phases/{phase_id}", response_model=ProjectPhaseResponse)
async def update_project_phase_status(
    project_id: str,
    phase_id: str,
    payload: ProjectPhaseStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPhaseResponse:
    link = await phase_service.update_project_phase_status(
        db, project_id, phase_id, user, status=payload.status, note=payload.note
    )
    phase = await phase_service.get_phase_or_404(db, phase_id)
    return ProjectPhaseResponse(
        id=link.id,
        phase_id=link.phase_id,
        phase_name=phase.name,
        phase_description=phase.description,
        status=link.status,
    )
