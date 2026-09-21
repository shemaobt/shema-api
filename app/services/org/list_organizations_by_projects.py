from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.org import Organization
from app.db.models.project import ProjectOrganizationAccess


async def list_organizations_by_projects(
    db: AsyncSession, project_ids: list[str], org_ids: list[str] | None = None
) -> list[Organization]:
    """The organizations a non-admin reaches: those on their projects, plus the ones they manage.

    Scoping by project alone was rejected because it hid an organization from the very person
    who runs it: managing an organization is authority in its own right, and
    ``get_organization_stats`` already answers a direct manager. Someone who manages an
    organization but no project would otherwise pass the console gate and read an empty list.
    """
    scopes = []
    if project_ids:
        scopes.append(
            Organization.id.in_(
                select(ProjectOrganizationAccess.organization_id)
                .where(ProjectOrganizationAccess.project_id.in_(project_ids))
                .distinct()
            )
        )
    if org_ids:
        scopes.append(Organization.id.in_(org_ids))
    if not scopes:
        return []
    stmt = select(Organization).where(or_(*scopes)).order_by(Organization.name)
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
