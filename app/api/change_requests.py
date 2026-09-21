from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.change_request import (
    ChangeRequestCreate,
    ChangeRequestKind,
    ChangeRequestResponse,
    ChangeRequestReview,
    ChangeRequestStatus,
)
from app.services import change_request_service

router = APIRouter()


@router.post("", response_model=ChangeRequestResponse, status_code=201)
async def create_change_request(
    payload: ChangeRequestCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChangeRequestResponse:
    request = await change_request_service.create_change_request(db, user.id, payload)
    return change_request_service.to_change_request_response(request, user)


@router.get("/mine", response_model=list[ChangeRequestResponse])
async def list_my_change_requests(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChangeRequestResponse]:
    rows = await change_request_service.list_my_change_requests(db, user.id)
    return [
        change_request_service.to_change_request_response(request, requester)
        for request, requester in rows
    ]


@router.get("", response_model=list[ChangeRequestResponse])
async def list_change_requests(
    kind: ChangeRequestKind | None = Query(None),
    status: ChangeRequestStatus | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> list[ChangeRequestResponse]:
    rows = await change_request_service.list_change_requests(db, kind, status)
    return [
        change_request_service.to_change_request_response(request, requester)
        for request, requester in rows
    ]


@router.patch("/{request_id}/review", response_model=ChangeRequestResponse)
async def review_change_request(
    request_id: str,
    payload: ChangeRequestReview,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_platform_admin),
) -> ChangeRequestResponse:
    request, requester = await change_request_service.review_change_request(
        db, actor, request_id, payload.status, payload.reason, payload.grant_manager_access
    )
    return change_request_service.to_change_request_response(request, requester)
