from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.db.models.auth import User
from app.db.models.project import Project, ProjectInvite
from app.services.project.grant_user_access import grant_user_access


async def create_invite(
    db: AsyncSession,
    project_id: str,
    email: str,
    role: str,
    invited_by: str,
) -> ProjectInvite:
    """Open — or refresh — a pending project invite for a registered address.

    A platform admin is refused here rather than at acceptance. ``grant_user_access``
    already refuses to link one, so an invite they can never spend would sit pending
    forever with decline as its only exit; the invite that is never written is the one
    nobody has to explain.
    """
    user_stmt = select(User).where(User.email == email, User.is_active.is_(True))
    invitee = (await db.execute(user_stmt)).scalar_one_or_none()
    if invitee is None:
        raise NotFoundError("No registered user found with that email")
    if invitee.is_platform_admin:
        raise ValidationError(
            "Platform admins cannot be invited to a project; they already manage every project."
        )

    stmt = select(ProjectInvite).where(
        ProjectInvite.project_id == project_id,
        ProjectInvite.email == email,
        ProjectInvite.status == "pending",
    )
    result = await db.execute(stmt)
    existing = result.scalar_one_or_none()
    if existing:
        existing.role = role
        existing.invited_by = invited_by
        existing.created_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(existing)
        return existing

    invite = ProjectInvite(
        project_id=project_id,
        email=email,
        role=role,
        invited_by=invited_by,
        app_key="oral-collector",
    )
    db.add(invite)
    await db.commit()
    await db.refresh(invite)
    return invite


async def list_user_invites(db: AsyncSession, user_email: str) -> list[tuple[ProjectInvite, str]]:

    stmt = (
        select(ProjectInvite, Project.name)
        .join(Project, Project.id == ProjectInvite.project_id)
        .where(
            ProjectInvite.email == user_email,
            ProjectInvite.status == "pending",
        )
        .order_by(ProjectInvite.created_at.desc())
    )
    result = await db.execute(stmt)
    return [(row[0], row[1]) for row in result.all()]


async def accept_invite(
    db: AsyncSession, invite_id: str, user_id: str, user_email: str
) -> ProjectInvite:

    invite = await _get_invite_for_user(db, invite_id, user_email)

    await grant_user_access(db, invite.project_id, user_id, role=invite.role)

    invite.status = "accepted"
    invite.accepted_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(invite)
    return invite


async def decline_invite(db: AsyncSession, invite_id: str, user_email: str) -> ProjectInvite:

    invite = await _get_invite_for_user(db, invite_id, user_email)

    invite.status = "declined"
    await db.commit()
    await db.refresh(invite)
    return invite


async def _get_invite_for_user(db: AsyncSession, invite_id: str, user_email: str) -> ProjectInvite:

    stmt = select(ProjectInvite).where(ProjectInvite.id == invite_id)
    result = await db.execute(stmt)
    invite = result.scalar_one_or_none()
    if not invite:
        raise NotFoundError("Invite not found")
    if invite.email != user_email:
        raise AuthorizationError("This invite does not belong to you")
    if invite.status != "pending":
        raise ConflictError(f"Invite has already been {invite.status}")
    return invite
