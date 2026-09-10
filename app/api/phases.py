from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.phase import (
    DependencyCreate,
    PhaseCreate,
    PhaseDependencyResponse,
    PhaseResponse,
    PhasesWithDepsResponse,
    PhaseUpdate,
)
from app.services import phase_service

router = APIRouter()


@router.post("", response_model=PhaseResponse, status_code=status.HTTP_201_CREATED)
async def create_phase(
    payload: PhaseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> PhaseResponse:
    phase = await phase_service.create_phase(db, payload)
    return PhaseResponse.model_validate(phase)


@router.get("", response_model=list[PhaseResponse])
async def list_phases(
    project_id: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PhaseResponse]:
    phases = await phase_service.list_phases(db, project_id=project_id)
    return [PhaseResponse.model_validate(phase) for phase in phases]


@router.get("/with-dependencies", response_model=PhasesWithDepsResponse)
async def list_phases_with_dependencies(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PhasesWithDepsResponse:
    return await phase_service.list_all_phases_with_deps(db)


@router.get("/{phase_id}", response_model=PhaseResponse)
async def get_phase(
    phase_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PhaseResponse:
    phase = await phase_service.get_phase_or_404(db, phase_id)
    project_ids = await phase_service.list_projects_for_phase(db, phase_id)
    return PhaseResponse.model_validate(phase).model_copy(update={"project_ids": project_ids})


@router.patch("/{phase_id}", response_model=PhaseResponse)
async def update_phase(
    phase_id: str,
    payload: PhaseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> PhaseResponse:
    phase = await phase_service.update_phase(db, phase_id, payload)
    return PhaseResponse.model_validate(phase)


@router.delete("/{phase_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phase(
    phase_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> None:
    await phase_service.delete_phase(db, phase_id)


@router.post(
    "/{phase_id}/dependencies",
    response_model=PhaseDependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_dependency(
    phase_id: str,
    payload: DependencyCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> PhaseDependencyResponse:
    dep = await phase_service.add_dependency(db, phase_id, payload.depends_on_id)
    return PhaseDependencyResponse.model_validate(dep)


@router.delete("/{phase_id}/dependencies/{depends_on_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_dependency(
    phase_id: str,
    depends_on_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_platform_admin),
) -> None:
    await phase_service.remove_dependency(db, phase_id, depends_on_id)


@router.get("/{phase_id}/dependencies", response_model=list[PhaseDependencyResponse])
async def list_dependencies(
    phase_id: str,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[PhaseDependencyResponse]:
    deps = await phase_service.list_dependencies(db, phase_id)
    return [PhaseDependencyResponse.model_validate(d) for d in deps]
