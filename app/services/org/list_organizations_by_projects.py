from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Organization
from app.db.models.project import ProjectOrganizationAccess


async def list_organizations_by_projects(
    db: AsyncSession, project_ids: list[str]
) -> list[Organization]:
    if not project_ids:
        return []
    org_ids_subq = (
        select(ProjectOrganizationAccess.organization_id)
        .where(ProjectOrganizationAccess.project_id.in_(project_ids))
        .distinct()
    )
    stmt = select(Organization).where(Organization.id.in_(org_ids_subq)).order_by(Organization.name)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
