from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.public_request import PublicRequest
from app.services.language.get_language_or_404 import get_language_or_404
from app.services.public_request.ensure_language_available import ensure_language_available


async def create_project_request(
    db: AsyncSession,
    requester_name: str,
    requester_email: str,
    name: str,
    language_id: str | None = None,
    description: str | None = None,
    new_language_name: str | None = None,
    new_language_code: str | None = None,
) -> PublicRequest:
    normalized_new_code: str | None = None
    if language_id:
        await get_language_or_404(db, language_id)
        new_language_name = None
    elif new_language_name and new_language_code:
        normalized_new_code = new_language_code.lower()
        new_language_name = new_language_name.strip()
        await ensure_language_available(db, new_language_name, normalized_new_code)
    else:
        raise ValidationError("Select an existing language or propose a new one (name and code)")

    request = PublicRequest(
        kind="create_project",
        requester_name=requester_name,
        requester_email=requester_email,
        name=name,
        language_id=language_id,
        new_language_name=new_language_name,
        new_language_code=normalized_new_code,
        description=description,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request
