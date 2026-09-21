from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.user import UserListResponse, UserRoleResponse, UserRoleUpdate, UserUpdate
from app.services import user_service

router = APIRouter()


@router.get("", response_model=list[UserListResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> list[UserListResponse]:
    users = await user_service.list_users(db)
    manager_ids = await user_service.get_manager_user_ids(db, [u.id for u in users])
    return [user_service.build_user_list_response(u, is_manager=u.id in manager_ids) for u in users]


@router.get("/search", response_model=list[UserListResponse])
async def search_users(
    q: str = "",
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[UserListResponse]:
    users = await user_service.search_users(db, q)
    manager_ids = await user_service.get_manager_user_ids(db, [u.id for u in users])
    return [user_service.build_user_list_response(u, is_manager=u.id in manager_ids) for u in users]


@router.get("/{user_id}", response_model=UserListResponse)
async def get_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> UserListResponse:
    user = await user_service.get_user_by_id(db, user_id)
    manager_ids = await user_service.get_manager_user_ids(db, [user.id])
    return user_service.build_user_list_response(user, is_manager=user.id in manager_ids)


@router.patch("/{user_id}", response_model=UserListResponse)
async def update_user(
    user_id: str,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> UserListResponse:
    user = await user_service.update_user(
        db,
        user_id,
        current_user,
        is_active=payload.is_active,
        is_platform_admin=payload.is_platform_admin,
        avatar_url=payload.avatar_url,
    )
    manager_ids = await user_service.get_manager_user_ids(db, [user.id])
    return user_service.build_user_list_response(user, is_manager=user.id in manager_ids)


@router.put("/{user_id}/role", response_model=UserListResponse)
async def set_user_role(
    user_id: str,
    payload: UserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
) -> UserListResponse:
    return await user_service.set_user_role(
        db,
        user_id,
        current_user,
        role=payload.role,
        project_ids=payload.project_ids,
    )


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
    _: User = Depends(require_platform_admin),
) -> list[UserRoleResponse]:
    roles = await user_service.list_user_roles(db, user_id)
    return [
        UserRoleResponse(app_key=app_key, role_key=role_key, granted_at=granted_at)
        for app_key, role_key, granted_at in roles
    ]
