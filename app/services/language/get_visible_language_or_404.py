from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.language import Language
from app.services.language.get_language_or_404 import get_language_or_404


async def get_visible_language_or_404(db: AsyncSession, language_id: str, actor: User) -> Language:
    """A deactivated language reads as 404 to everyone but a platform admin.

    404 rather than 403 is the deliberate half. Deactivation takes a language out of the
    catalogue; it is not a record withheld from someone who may ask for it, and answering 403
    would confirm the code is taken and invite exactly that request. The admin keeps reading it
    because the console has to show a deactivated language to reactivate it.
    """
    language = await get_language_or_404(db, language_id)
    if not language.is_active and not actor.is_platform_admin:
        raise NotFoundError(f"Language {language_id} not found")
    return language
