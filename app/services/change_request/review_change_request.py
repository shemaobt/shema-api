from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import User
from app.db.models.change_request import ChangeRequest, ChangeRequestKind, ChangeRequestStatus
from app.db.models.language import Language
from app.services.language.get_language_by_code import get_language_by_code
from app.services.language.get_language_or_404 import get_language_or_404
from app.services.project.create_project import create_project


async def review_change_request(
    db: AsyncSession,
    reviewer: User,
    request_id: str,
    status: ChangeRequestStatus,
    reason: str | None,
    grant_manager_access: bool,
) -> tuple[ChangeRequest, User]:
    request = await db.get(ChangeRequest, request_id)
    if request is None:
        raise NotFoundError("Change request not found")
    if request.status != ChangeRequestStatus.PENDING:
        raise ConflictError("This request has already been reviewed")

    if status == ChangeRequestStatus.APPROVED:
        request.created_entity_id = await _apply(db, request, grant_manager_access)

    request.status = status
    request.reviewed_by = reviewer.id
    request.reviewed_at = datetime.now(UTC)
    request.review_reason = reason
    request.grant_manager_access = grant_manager_access
    await db.commit()
    await db.refresh(request)

    requester = await db.get(User, request.requester_user_id)
    if requester is None:
        raise NotFoundError("Requester not found")
    return request, requester


async def _apply(db: AsyncSession, request: ChangeRequest, grant_manager_access: bool) -> str:
    if request.kind == ChangeRequestKind.CREATE_PROJECT:
        name = request.name
        assert name is not None
        project_language_id = request.language_id or await _create_requested_language(db, request)
        project = await create_project(
            db,
            name=name,
            language_id=project_language_id,
            description=request.description,
            creator_user_id=request.requester_user_id if grant_manager_access else None,
        )
        return project.id

    if request.kind == ChangeRequestKind.CREATE_LANGUAGE:
        name = request.name
        code = request.code
        assert name is not None and code is not None
        if await get_language_by_code(db, code):
            raise ConflictError("Language code already exists")
        language = Language(name=name, code=code, created_by=request.requester_user_id)
        db.add(language)
        await db.commit()
        await db.refresh(language)
        return language.id

    language_id = request.language_id
    assert language_id is not None
    language = await get_language_or_404(db, language_id)
    new_code = request.code
    if new_code and new_code != language.code:
        if await get_language_by_code(db, new_code):
            raise ConflictError("Language code already exists")
        language.code = new_code
    new_name = request.name
    if new_name:
        language.name = new_name
    await db.commit()
    await db.refresh(language)
    return language.id


async def _create_requested_language(db: AsyncSession, request: ChangeRequest) -> str:
    name = request.new_language_name
    code = request.new_language_code
    assert name is not None and code is not None
    if await get_language_by_code(db, code):
        raise ConflictError("Language code already exists")
    language = Language(name=name, code=code, created_by=request.requester_user_id)
    db.add(language)
    await db.flush()
    return language.id
