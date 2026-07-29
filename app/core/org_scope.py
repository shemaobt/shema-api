from fastapi import Depends
from sqlalchemy import select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.db.models.auth import User
from app.db.models.org import MemberRole, Organization, OrganizationMember


async def get_managed_project_ids(db: AsyncSession, user_id: str) -> list[str]:
    from app.services.project.get_managed_project_ids import (
        get_managed_project_ids as _get_managed_project_ids,
    )

    return await _get_managed_project_ids(db, user_id)


async def get_managed_org_ids(db: AsyncSession, user_id: str) -> list[str]:
    from_members = select(OrganizationMember.organization_id.label("org_id")).where(
        OrganizationMember.user_id == user_id,
        OrganizationMember.role == MemberRole.MANAGER,
    )

    from_orgs = select(Organization.id.label("org_id")).where(Organization.manager_id == user_id)

    combined = union(from_members, from_orgs).subquery()
    result = await db.execute(select(combined.c.org_id))
    return sorted(result.scalars().all())


async def get_current_user_managed_org_ids(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[str]:
    return await get_managed_org_ids(db, user.id)
