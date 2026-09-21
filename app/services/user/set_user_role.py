from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.project import Project, ProjectUserAccess
from app.models.user import UserListResponse, UserRole
from app.services.user.build_user_list_response import build_user_list_response
from app.services.user.get_manager_user_ids import get_manager_user_ids
from app.services.user.get_user_by_id import get_user_by_id


async def set_user_role(
    db: AsyncSession,
    user_id: str,
    acting_user: User,
    role: UserRole,
    project_ids: list[str] | None = None,
) -> UserListResponse:
    user = await get_user_by_id(db, user_id)
    if user.id == acting_user.id:
        raise AuthorizationError("Platform admins cannot change their own role")

    if role == "platform_admin":
        user.is_platform_admin = True
    elif role == "manager":
        user.is_platform_admin = False
        await _grant_manager_access(db, user, project_ids)
    else:
        user.is_platform_admin = False
        await _demote_manager_access(db, user)

    await db.commit()
    await db.refresh(user)
    manager_ids = await get_manager_user_ids(db, [user.id])
    return build_user_list_response(user, is_manager=user.id in manager_ids)


async def _grant_manager_access(
    db: AsyncSession, user: User, project_ids: list[str] | None
) -> None:
    if not project_ids:
        if not await get_manager_user_ids(db, [user.id]):
            raise ValidationError(
                "project_ids is required when promoting a user who manages no projects"
            )
        return

    unique_ids = list(dict.fromkeys(project_ids))
    found_stmt: Select[tuple[str]] = select(Project.id).where(Project.id.in_(unique_ids))
    found = set((await db.execute(found_stmt)).scalars().all())
    for project_id in unique_ids:
        if project_id not in found:
            raise NotFoundError(f"Project {project_id} not found")

    access_stmt: Select[tuple[ProjectUserAccess]] = select(ProjectUserAccess).where(
        ProjectUserAccess.user_id == user.id,
        ProjectUserAccess.project_id.in_(unique_ids),
    )
    existing = {access.project_id: access for access in (await db.execute(access_stmt)).scalars()}
    for project_id in unique_ids:
        access = existing.get(project_id)
        if access:
            access.role = "manager"
        else:
            db.add(ProjectUserAccess(project_id=project_id, user_id=user.id, role="manager"))


async def _demote_manager_access(db: AsyncSession, user: User) -> None:
    stmt: Select[tuple[ProjectUserAccess]] = select(ProjectUserAccess).where(
        ProjectUserAccess.user_id == user.id,
        ProjectUserAccess.role == "manager",
    )
    for access in (await db.execute(stmt)).scalars():
        access.role = "member"
