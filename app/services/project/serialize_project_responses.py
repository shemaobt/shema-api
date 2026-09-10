from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.project import Project
from app.models.project import ProjectResponse
from app.services.project.count_project_team_sizes import count_project_team_sizes


async def serialize_projects(db: AsyncSession, projects: list[Project]) -> list[ProjectResponse]:
    team_sizes = await count_project_team_sizes(db, [p.id for p in projects])
    return [
        ProjectResponse.model_validate(p).model_copy(update={"team_size": team_sizes.get(p.id, 0)})
        for p in projects
    ]


async def serialize_project(db: AsyncSession, project: Project) -> ProjectResponse:
    (response,) = await serialize_projects(db, [project])
    return response
