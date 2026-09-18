from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.language import Language
from app.services.language.get_language_or_404 import get_language_or_404


async def deactivate_language(db: AsyncSession, language_id: str, actor: User) -> Language:
    if not actor.is_platform_admin:
        raise AuthorizationError("Only platform admins can deactivate languages")

    language = await get_language_or_404(db, language_id)
    language.is_active = False
    await db.commit()
    await db.refresh(language)
    return language
