from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.language import Language


async def list_languages(
    db: AsyncSession, actor: User, *, include_inactive: bool = False
) -> list[Language]:
    stmt: Select[tuple[Language]] = select(Language).order_by(Language.code)
    if not (include_inactive and actor.is_platform_admin):
        stmt = stmt.where(Language.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())
