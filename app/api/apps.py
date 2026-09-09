from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_middleware import get_current_user, require_platform_admin
from app.core.database import get_db
from app.db.models.auth import User
from app.models.app import (
    AppCreate,
    AppResponse,
    AppRoleCreate,
    AppRoleResponse,
    AppUpdate,
    UserAppResponse,
)
from app.services import app_service

router = APIRouter()


@router.get("", response_model=list[AppResponse])
async def list_apps(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> list[AppResponse]:
    apps = await app_service.list_apps(db)
    return [AppResponse.model_validate(a) for a in apps]


@router.get("/my-apps", response_model=list[UserAppResponse])
async def my_apps(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[UserAppResponse]:
    return await app_service.list_user_apps_display(
        db, current_user.id, is_admin=current_user.is_platform_admin
    )


@router.post("", response_model=AppResponse, status_code=201)
async def create_app(
    payload: AppCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AppResponse:
    app = await app_service.create_app(
        db,
        app_key=payload.app_key,
        name=payload.name,
        description=payload.description,
        icon_url=payload.icon_url,
        app_url=payload.app_url,
        ios_url=payload.ios_url,
        android_url=payload.android_url,
        platforms=payload.platforms,
        is_active=payload.is_active if payload.is_active is not None else True,
        auto_approve=payload.auto_approve if payload.auto_approve is not None else False,
    )
    return AppResponse.model_validate(app)


@router.get("/{app_id}", response_model=AppResponse)
async def get_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> AppResponse:
    app = await app_service.get_app_or_404(db, app_id)
    return AppResponse.model_validate(app)


@router.patch("/{app_id}", response_model=AppResponse)
async def update_app(
    app_id: str,
    payload: AppUpdate,
    db: AsyncSession = Depends(get_db),
    actor: User = Depends(require_platform_admin),
) -> AppResponse:
    app = await app_service.update_app(
        db,
        app_id,
        name=payload.name,
        description=payload.description,
        icon_url=payload.icon_url,
        app_url=payload.app_url,
        ios_url=payload.ios_url,
        android_url=payload.android_url,
        platforms=payload.platforms,
        is_active=payload.is_active,
        auto_approve=payload.auto_approve,
        actor=actor,
    )
    return AppResponse.model_validate(app)


@router.delete("/{app_id}", status_code=204)
async def delete_app(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    await app_service.delete_app(db, app_id)


@router.get("/{app_id}/roles", response_model=list[AppRoleResponse])
async def list_app_roles(
    app_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[AppRoleResponse]:
    roles = await app_service.list_app_roles(db, app_id)
    return [AppRoleResponse.model_validate(r) for r in roles]


@router.post("/{app_id}/roles", response_model=AppRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_app_role(
    app_id: str,
    payload: AppRoleCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> AppRoleResponse:
    role = await app_service.create_app_role(
        db,
        app_id,
        role_key=payload.role_key,
        label=payload.label,
        description=payload.description,
    )
    return AppRoleResponse.model_validate(role)


@router.delete("/{app_id}/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_app_role(
    app_id: str,
    role_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_platform_admin),
) -> None:
    await app_service.delete_app_role(db, app_id, role_id)
