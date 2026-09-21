from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.language import Language
from app.services.language.get_language_by_code import get_language_by_code


async def get_visible_language_by_code_or_404(db: AsyncSession, code: str, actor: User) -> Language:
    """The same visibility rule as ``get_visible_language_or_404``, reached by code.

    Lookup by code is the path that would leak the most: a caller probing codes learns from a
    403 that the code exists and is merely switched off, which is the one fact deactivation is
    meant to stop handing out. A missing language and a deactivated one answer identically.
    """
    language = await get_language_by_code(db, code)
    if language is None or (not language.is_active and not actor.is_platform_admin):
        raise NotFoundError("Language not found")
    return language
