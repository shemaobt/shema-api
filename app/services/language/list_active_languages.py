from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language


async def list_active_languages(db: AsyncSession) -> list[Language]:
    """The languages a visitor with no account may choose from.

    Kept apart from ``list_languages``, which takes an actor only so it can decide whether
    ``include_inactive`` is honoured. The public form has no actor to hand it, and inventing a
    stand-in user would have put an authorisation question where there is no authorisation.
    This one cannot be asked for a deactivated language at all.
    """
    stmt: Select[tuple[Language]] = (
        select(Language).where(Language.is_active.is_(True)).order_by(Language.code)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())
