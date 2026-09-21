from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.models.oc_project import (
    OCProjectListResponse,
    OCProjectStatsResponse,
)
from app.services.oral_collector import project_service
from app.services.oral_collector.project_member_counts import get_member_counts

projects_router = APIRouter()


@projects_router.get("", response_model=list[OCProjectListResponse])
async def list_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[OCProjectListResponse]:

    projects = await project_service.list_user_projects(db, user.id)
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    counts = await get_member_counts(db, project_ids)
    stats = await project_service.get_projects_batch_stats(db, project_ids)

    return [
        OCProjectListResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            language_id=p.language_id,
            latitude=p.latitude,
            longitude=p.longitude,
            location_display_name=p.location_display_name,
            image_url=p.image_url,
            created_at=p.created_at,
            updated_at=p.updated_at,
            member_count=counts.get(p.id, 0),
            recording_count=int(stats.get(p.id, {}).get("recordings", 0)),
            total_duration_seconds=float(stats.get(p.id, {}).get("duration", 0.0)),
            storyteller_count=int(stats.get(p.id, {}).get("storytellers", 0)),
        )
        for p in projects
    ]


@projects_router.get("/{project_id}/stats", response_model=OCProjectStatsResponse)
async def get_project_stats(
    project_id: str,
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> OCProjectStatsResponse:

    return await project_service.get_project_stats(db, project_id)
