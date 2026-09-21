from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from app.db.models.project import Project


async def list_languages_by_projects(db: AsyncSession, project_ids: list[str]) -> list[Language]:
    """The active languages of a non-admin's projects.

    Deactivated ones are left out and there is no ``include_inactive`` here to ask for them:
    this is the non-admin path, and the rule it answers to is the one
    ``get_visible_language_or_404`` states — a deactivated language reads as absent to
    everyone but a platform admin. Letting it through a list while a direct read of it
    answers 404 would be the same language saying two things.
    """
    if not project_ids:
        return []
    language_ids_subq = select(Project.language_id).where(Project.id.in_(project_ids)).distinct()
    stmt = (
        select(Language)
        .where(Language.id.in_(language_ids_subq), Language.is_active.is_(True))
        .order_by(Language.code)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
