from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.user import UserListResponse, UserRoleResponse, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("", response_model=list[UserListResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> list[UserListResponse]:
    users = await user_service.list_users(db)
    return [UserListResponse.model_validate(u) for u in users]


@router.get("/search", response_model=list[UserListResponse])
async def search_users(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[UserListResponse]:
    users = await user_service.search_users(db, q)
    return [UserListResponse.model_validate(u) for u in users]


@router.get("/{user_id}", response_model=UserListResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> UserListResponse:
    user = await user_service.get_user_by_id(db, user_id)
    return UserListResponse.model_validate(user)


@router.patch("/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> UserListResponse:
    user = await user_service.update_user(db, user_id, **payload.model_dump(exclude_unset=True))
    return UserListResponse.model_validate(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    await user_service.delete_user(db, user_id)


@router.get("/{user_id}/roles", response_model=list[UserRoleResponse])
async def list_user_roles(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[UserRoleResponse]:
    roles = await user_service.list_user_roles(db, user_id)
    return [
        UserRoleResponse(app_key=app_key, role_key=role_key, granted_at=granted_at)
        for app_key, role_key, granted_at in roles
    ]
