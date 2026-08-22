from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.public_request import PublicRequest
from app.services.public_request.ensure_language_available import ensure_language_available


async def create_language_request(
    db: AsyncSession,
    requester_name: str,
    requester_email: str,
    name: str,
    code: str,
    description: str | None = None,
) -> PublicRequest:
    normalized_code = code.lower()
    await ensure_language_available(db, name, normalized_code)

    request = PublicRequest(
        kind="create_language",
        requester_name=requester_name,
        requester_email=requester_email,
        name=name.strip(),
        code=normalized_code,
        description=description,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)
    return request
