from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import PublicRequestKind, PublicRequestStatus
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.auth import User
from app.db.models.language import Language
from app.db.models.public_request import PublicRequest
from app.services.language.get_language_by_code import get_language_by_code
from app.services.project.create_project import create_project


async def review_public_request(
    db: AsyncSession,
    reviewer: User,
    request_id: str,
    status: PublicRequestStatus,
    reason: str | None,
) -> PublicRequest:
    request = await db.get(PublicRequest, request_id)
    if request is None:
        raise NotFoundError("Public request not found")
    if request.status != PublicRequestStatus.PENDING:
        raise ConflictError("This request has already been reviewed")

    if status == PublicRequestStatus.APPROVED:
        request.created_entity_id = await _apply(db, request)

    request.status = status
    request.reviewed_by = reviewer.id
    request.reviewed_at = datetime.now(UTC)
    request.review_reason = reason
    await db.commit()
    await db.refresh(request)
    return request


async def _apply(db: AsyncSession, request: PublicRequest) -> str:
    if request.kind == PublicRequestKind.CREATE_PROJECT:
        language_id = request.language_id or await _create_requested_language(db, request)
        project = await create_project(
            db,
            name=request.name,
            language_id=language_id,
            description=request.description,
        )
        return project.id

    code = request.code
    if code is None:
        raise ValidationError("This request has no language code to create")
    if await get_language_by_code(db, code):
        raise ConflictError("Language code already exists")
    language = Language(name=request.name, code=code)
    db.add(language)
    await db.flush()
    return language.id


async def _create_requested_language(db: AsyncSession, request: PublicRequest) -> str:
    """The new language a project request asked for, refused in words if it is half-filled.

    ``assert`` was wrong twice here: it answers 500 to a reviewer who can do nothing about it,
    and ``python -O`` drops it, which would carry a ``None`` name into the row instead. Rows
    written before ``PublicProjectRequestCreate`` required both fields can still be pending,
    so the write path states the rule even though the edge now does too.
    """
    name = request.new_language_name
    code = request.new_language_code
    if name is None or code is None:
        raise ValidationError("This request has no new language to create")
    if await get_language_by_code(db, code):
        raise ConflictError("Language code already exists")
    language = Language(name=name, code=code)
    db.add(language)
    await db.flush()
    return language.id
