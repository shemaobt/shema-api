from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.db.models.change_request import ChangeRequest, ChangeRequestKind
from app.db.models.language import Language
from app.db.models.org import MemberRole
from app.db.models.project import Project, ProjectUserAccess
from app.models.change_request import ChangeRequestCreate


async def create_change_request(
    db: AsyncSession, requester_id: str, payload: ChangeRequestCreate
) -> ChangeRequest:
    if payload.kind == ChangeRequestKind.CREATE_PROJECT:
        if not payload.name:
            raise ValidationError("A project request needs a name")
        wants_new_language = bool(payload.new_language_name or payload.new_language_code)
        if payload.language_id and wants_new_language:
            raise ValidationError("Pick an existing language or request a new one, not both")
        if payload.language_id:
            if await db.get(Language, payload.language_id) is None:
                raise NotFoundError("Language not found")
        elif wants_new_language:
            if not payload.new_language_name or not payload.new_language_code:
                raise ValidationError("A new language needs a name and a 3-character code")
            if len(payload.new_language_code) != 3:
                raise ValidationError("A language code must be exactly 3 characters")
        else:
            raise ValidationError("A project request needs a language")
    elif payload.kind == ChangeRequestKind.CREATE_LANGUAGE:
        if not payload.name or not payload.code or len(payload.code) != 3:
            raise ValidationError("A language request needs a name and a 3-character code")
    else:
        if not payload.language_id or (payload.name is None and payload.code is None):
            raise ValidationError("An edit request needs a target language and a new name or code")
        if payload.code is not None and len(payload.code) != 3:
            raise ValidationError("A language code must be exactly 3 characters")
        await _assert_language_in_managed_project(db, requester_id, payload.language_id)

    request = ChangeRequest(
        kind=payload.kind,
        requester_user_id=requester_id,
        name=payload.name,
        code=payload.code.lower() if payload.code else None,
        description=payload.description,
        language_id=payload.language_id,
        new_language_name=payload.new_language_name,
        new_language_code=payload.new_language_code.lower() if payload.new_language_code else None,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request


async def _assert_language_in_managed_project(
    db: AsyncSession, requester_id: str, language_id: str
) -> None:
    stmt = (
        select(Project.id)
        .join(ProjectUserAccess, ProjectUserAccess.project_id == Project.id)
        .where(
            Project.language_id == language_id,
            ProjectUserAccess.user_id == requester_id,
            ProjectUserAccess.role == MemberRole.MANAGER,
        )
        .limit(1)
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise AuthorizationError("You can only request edits for languages used by your projects")
