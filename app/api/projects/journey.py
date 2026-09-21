from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.projects._deps import assert_project_access
from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.journey import PhaseStatusLogResponse, ProjectJourneyAssign
from app.models.project import ProjectResponse
from app.services import phase_service, project_service

router = APIRouter()


@router.put("/{project_id}/journey", response_model=ProjectResponse)
async def assign_project_journey(
    project_id: str,
    payload: ProjectJourneyAssign,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> ProjectResponse:
    project = await project_service.assign_journey(db, project_id, payload.journey_id)
    return ProjectResponse.model_validate(project)


@router.get("/{project_id}/phases/status-log", response_model=list[PhaseStatusLogResponse])
async def list_project_phase_status_logs(
    project_id: str,
    phase_id: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[PhaseStatusLogResponse]:
    await assert_project_access(db, user, project_id)
    return await phase_service.list_phase_status_logs(db, project_id, phase_id=phase_id)
