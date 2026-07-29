from sqlalchemy.ext.asyncio import AsyncSession

from app.core.org_scope import get_managed_project_ids
from app.db.models.auth import User
from app.db.models.project import Project
from app.services.project.list_all_projects import list_all_projects
from app.services.project.list_projects_by_ids import list_projects_by_ids
from app.services.project.list_projects_by_organization import (
    list_projects_by_organization,
)


async def list_projects_for_user(
    db: AsyncSession,
    user: User,
    organization_id: str | None = None,
    language_id: str | None = None,
) -> list[Project]:
    if user.is_platform_admin:
        if organization_id:
            projects = await list_projects_by_organization(db, organization_id)
        else:
            projects = await list_all_projects(db)
    else:
        managed_project_ids = await get_managed_project_ids(db, user.id)
        projects = await list_projects_by_ids(db, managed_project_ids)
        if organization_id:
            org_project_ids = {
                p.id for p in await list_projects_by_organization(db, organization_id)
            }
            projects = [p for p in projects if p.id in org_project_ids]

    if language_id is not None:
        projects = [p for p in projects if p.language_id == language_id]

    return projects
