from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.db.models.project import ProjectUserAccess
from app.models.oc_storyteller import StorytellerCreate, StorytellerUpdate
from app.services.oral_collector.require_access import require_project_access
from app.services.oral_collector.review_flags import recompute_review_flags


async def list_project_storytellers(db: AsyncSession, project_id: str) -> list[OC_Storyteller]:
    """Return all storytellers for a project, ordered by name."""
    stmt = (
        select(OC_Storyteller)
        .where(OC_Storyteller.project_id == project_id)
        .order_by(OC_Storyteller.name)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_storyteller(db: AsyncSession, storyteller_id: str) -> OC_Storyteller:
    """Fetch a storyteller by id or raise NotFoundError."""
    stmt = select(OC_Storyteller).where(OC_Storyteller.id == storyteller_id)
    result = await db.execute(stmt)
    storyteller = result.scalar_one_or_none()
    if storyteller is None:
        raise NotFoundError("Storyteller not found")
    return storyteller


async def check_storyteller_access(
    db: AsyncSession, storyteller: OC_Storyteller, user_id: str
) -> None:
    """Raise AuthorizationError unless the user can modify the storyteller.

    Allowed: platform admins, project managers, or the storyteller's creator.
    """
    acting_user = await db.get(User, user_id)
    if acting_user is not None and acting_user.is_platform_admin:
        return
    if storyteller.created_by_user_id == user_id:
        return
    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == storyteller.project_id,
        ProjectUserAccess.user_id == user_id,
        ProjectUserAccess.role == "manager",
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise AuthorizationError(
            "Only the storyteller's creator, a project manager, "
            "or a platform admin can modify this storyteller"
        )


async def create_storyteller(
    db: AsyncSession,
    project_id: str,
    data: StorytellerCreate,
    user: User,
) -> OC_Storyteller:
    """Create a storyteller for a project. Any project member may create."""
    await require_project_access(db, project_id, user)
    if not data.external_acceptance_confirmed:
        raise ValidationError(
            "External acceptance validation is required before registering a storyteller"
        )

    storyteller = OC_Storyteller(
        project_id=project_id,
        name=data.name,
        sex=data.sex,
        age=data.age,
        location=data.location,
        dialect=data.dialect,
        external_acceptance_confirmed=True,
        external_acceptance_confirmed_at=datetime.now(UTC),
        external_acceptance_confirmed_by=user.id,
        created_by_user_id=user.id,
    )
    db.add(storyteller)
    await db.commit()
    await db.refresh(storyteller)
    return storyteller


async def update_storyteller(
    db: AsyncSession,
    storyteller_id: str,
    data: StorytellerUpdate,
    user_id: str,
) -> OC_Storyteller:
    """Update a storyteller. Allowed for the creator, project managers, or platform admins."""
    storyteller = await get_storyteller(db, storyteller_id)
    await check_storyteller_access(db, storyteller, user_id)

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        setattr(storyteller, field, value)
    await db.commit()
    await db.refresh(storyteller)
    return storyteller


async def delete_storyteller(
    db: AsyncSession,
    storyteller_id: str,
    user_id: str,
) -> None:
    """Delete a storyteller. Linked recordings keep their data; storyteller_id is set to NULL.

    The foreign key would already do the nulling, but it does it inside the database with no
    ORM object loaded, leaving the recordings' review flags claiming a storyteller that no
    longer exists. Applying the NULL here first makes the loss observable to the recompute.
    """
    storyteller = await get_storyteller(db, storyteller_id)
    await check_storyteller_access(db, storyteller, user_id)

    stmt = select(OC_Recording).where(OC_Recording.storyteller_id == storyteller_id)
    result = await db.execute(stmt)
    for recording in result.scalars().all():
        recording.storyteller_id = None
        recompute_review_flags(recording)

    await db.delete(storyteller)
    await db.commit()
