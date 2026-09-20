from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User

#: Below this the `%q%` search pages the whole table; the floor drops the empty/one-char dump.
MIN_SEARCH_QUERY_LENGTH = 2


async def search_users(db: AsyncSession, query: str) -> list[User]:
    term = query.strip()
    if len(term) < MIN_SEARCH_QUERY_LENGTH:
        return []
    pattern = f"%{term}%"
    stmt: Select[tuple[User]] = (
        select(User)
        .where(User.is_active.is_(True))
        .where(
            or_(
                User.email.ilike(pattern),
                User.display_name.ilike(pattern),
            )
        )
        .order_by(User.email)
        .limit(50)
    )
    result = await db.execute(stmt)
    return list(result.scalars().unique().all())
