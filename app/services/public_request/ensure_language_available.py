from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.language import Language
from app.db.models.public_request import PublicRequest


async def ensure_language_available(db: AsyncSession, name: str, code: str) -> None:
    lowered_name = name.strip().lower()
    lowered_code = code.strip().lower()

    existing_stmt: Select[tuple[Language]] = (
        select(Language)
        .where(
            or_(
                func.lower(Language.name) == lowered_name,
                Language.code == lowered_code,
            )
        )
        .limit(1)
    )
    existing = await db.execute(existing_stmt)
    if existing.scalar_one_or_none():
        raise ConflictError("A language with this name or code already exists")

    pending_stmt: Select[tuple[PublicRequest]] = (
        select(PublicRequest)
        .where(
            PublicRequest.status == "pending",
            or_(
                and_(
                    PublicRequest.kind == "create_language",
                    or_(
                        func.lower(PublicRequest.name) == lowered_name,
                        PublicRequest.code == lowered_code,
                    ),
                ),
                and_(
                    PublicRequest.kind == "create_project",
                    or_(
                        func.lower(PublicRequest.new_language_name) == lowered_name,
                        PublicRequest.new_language_code == lowered_code,
                    ),
                ),
            ),
        )
        .limit(1)
    )
    pending = await db.execute(pending_stmt)
    if pending.scalar_one_or_none():
        raise ConflictError("A pending request for this language name or code already exists")
