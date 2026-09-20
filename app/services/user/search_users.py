from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User

#: Shortest query the directory search will answer. Below this the endpoint is a
#: typeahead with nothing typed, and answering it dumps the whole user table (email,
#: display name and the platform-admin flag) to any caller who may search at all. Two
#: characters keeps the pick-a-user flows working while it stops being an enumeration
#: oracle; the console pickers only fire once the field holds a couple of characters.
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
