from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.language import Language
from app.services.language.get_language_by_code import get_language_by_code
from app.services.language.get_language_or_404 import get_language_or_404


async def update_language(
    db: AsyncSession,
    language_id: str,
    *,
    name: str | None = None,
    code: str | None = None,
) -> Language:
    language = await get_language_or_404(db, language_id)

    if code is not None:
        normalized = code.lower()
        if normalized != language.code:
            existing = await get_language_by_code(db, normalized)
            if existing is not None:
                raise ConflictError("Language code already exists")
        language.code = normalized

    if name is not None:
        language.name = name

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictError("Language code already exists") from exc
    await db.refresh(language)
    return language
