from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.org_scope import get_managed_org_ids
from app.db.models.project import ProjectOrganizationAccess
from app.services.project.get_managed_project_ids import get_managed_project_ids


async def list_managed_project_ids(db: AsyncSession, user_id: str) -> list[str]:
    """The projects this account operates — named manager, or through an organization.

    A composition of the two owners that already exist rather than a third rule:
    `get_managed_project_ids` answers "projects I was named manager of" and
    `get_managed_org_ids` answers "organizations I manage"; the only query added
    here is the one that turns the second into projects.

    Wider on purpose than PR #92's per-project `is_project_manager`, which asks
    whether someone may command a project's roster and deliberately admits only
    the named manager. This function answers a reader's question — what a
    Console operator may look at — and the Console's own definition of operator,
    in `require_admin_or_manager` and in the front's `isManager`, includes the
    manager of an organization. When #92 lands the two should be read side by
    side and the difference either kept on purpose or collapsed.
    """
    direct = await get_managed_project_ids(db, user_id)
    org_ids = await get_managed_org_ids(db, user_id)
    if not org_ids:
        return sorted(set(direct))

    result = await db.execute(
        select(ProjectOrganizationAccess.project_id).where(
            ProjectOrganizationAccess.organization_id.in_(org_ids)
        )
    )
    return sorted(set(direct) | set(result.scalars().all()))
