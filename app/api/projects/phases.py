from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects._deps import assert_project_access, assert_project_manager
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.db.models.phase import PhaseStatus
from app.models.phase import (
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


@router.patch("/{project_id}/phases/{phase_id}", response_model=ProjectPhaseResponse)
async def update_project_phase_status(
    project_id: str,
    phase_id: str,
    payload: ProjectPhaseStatusUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProjectPhaseResponse:
    await assert_project_manager(db, user, project_id)
    link = await phase_service.update_project_phase_status(db, project_id, phase_id, payload.status)
    phase = await phase_service.get_phase_or_404(db, phase_id)
    return ProjectPhaseResponse(
        id=link.id,
        phase_id=link.phase_id,
        phase_name=phase.name,
        phase_description=phase.description,
        status=PhaseStatus(link.status),
    )
