from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.language import Language
from app.services.language.get_language_or_404 import get_language_or_404


async def get_visible_language_or_404(db: AsyncSession, language_id: str, actor: User) -> Language:
    language = await get_language_or_404(db, language_id)
    if not language.is_active and not actor.is_platform_admin:
        raise NotFoundError(f"Language {language_id} not found")
    return language
