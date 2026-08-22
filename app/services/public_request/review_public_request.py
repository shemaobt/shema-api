from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import User
from app.db.models.language import Language
from app.db.models.public_request import PublicRequest
from app.services.language.get_language_by_code import get_language_by_code
from app.services.project.create_project import create_project


async def review_public_request(
    db: AsyncSession,
    reviewer: User,
    request_id: str,
    status: str,
    reason: str | None,
) -> PublicRequest:
    request = await db.get(PublicRequest, request_id)
    if request is None:
        raise NotFoundError("Public request not found")
    if request.status != "pending":
        raise ConflictError("This request has already been reviewed")

    if status == "approved":
        request.created_entity_id = await _apply(db, request)

    request.status = status
    request.reviewed_by = reviewer.id
    request.reviewed_at = datetime.now(UTC)
    request.review_reason = reason
    await db.commit()
    await db.refresh(request)
    return request


async def _apply(db: AsyncSession, request: PublicRequest) -> str:
    if request.kind == "create_project":
        language_id = request.language_id or await _create_requested_language(db, request)
        project = await create_project(
            db,
            name=request.name,
            language_id=language_id,
            description=request.description,
        )
        return project.id

    code = request.code
    assert code is not None
    if await get_language_by_code(db, code):
        raise ConflictError("Language code already exists")
    language = Language(name=request.name, code=code)
    db.add(language)
    await db.commit()
    await db.refresh(language)
    return language.id


async def _create_requested_language(db: AsyncSession, request: PublicRequest) -> str:
    name = request.new_language_name
    code = request.new_language_code
    assert name is not None and code is not None
    if await get_language_by_code(db, code):
        raise ConflictError("Language code already exists")
    language = Language(name=name, code=code)
    db.add(language)
    await db.flush()
    return language.id
