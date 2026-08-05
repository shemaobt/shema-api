from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.public_request import PublicRequestAdminResponse, PublicRequestReview
from app.services import public_request_service

router = APIRouter()


@router.get("", response_model=list[PublicRequestAdminResponse])
async def list_public_requests(
    kind: str | None = Query(default=None),
    status: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> list[PublicRequestAdminResponse]:
    requests = await public_request_service.list_public_requests(db, kind=kind, status=status)
    return [PublicRequestAdminResponse.model_validate(request) for request in requests]


@router.patch("/{request_id}/review", response_model=PublicRequestAdminResponse)
async def review_public_request(
    request_id: str,
    payload: PublicRequestReview,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_platform_admin),
) -> PublicRequestAdminResponse:
    request = await public_request_service.review_public_request(
        db, actor, request_id, payload.status, payload.reason
    )
    return PublicRequestAdminResponse.model_validate(request)
