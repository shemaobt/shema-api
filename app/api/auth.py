from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_user
from app.core.auth_middleware import get_current_user
from app.core.database import get_db
from app.core.org_scope import get_managed_org_ids
from app.db.models.auth import User
from app.models.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    MyManagedOrgsResponse,
    MyProjectRolesResponse,
    PasswordResetResponse,
    ProfileUpdate,
    ResetPasswordRequest,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserResponse,
    UserSignupRequest,
)
from app.models.role import MyRoleResponse
from app.services import auth_service, authorization_service, user_service
from app.services.project import list_user_project_roles

router = APIRouter()


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
        is_platform_admin=user.is_platform_admin,
        locale=user.locale,
    )


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: UserSignupRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await auth_service.signup_user(db, payload)
    access_token, refresh_token = await auth_service.issue_tokens(db, user)
    return AuthResponse(
        user=_user_response(user),
        tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token),
    )


@router.post("/login", response_model=AuthResponse)
async def login(payload: UserLoginRequest, db: AsyncSession = Depends(get_db)) -> AuthResponse:
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    access_token, refresh_token = await auth_service.issue_tokens(db, user)
    return AuthResponse(
        user=_user_response(user),
        tokens=TokenResponse(access_token=access_token, refresh_token=refresh_token),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: TokenRefreshRequest, db: AsyncSession = Depends(get_db)
) -> TokenResponse:
    access_token = await auth_service.refresh_access_token(db, payload.refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=payload.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: TokenRefreshRequest, db: AsyncSession = Depends(get_db)) -> None:
    await auth_service.revoke_refresh_token(db, payload.refresh_token)


@router.get("/me", response_model=UserResponse)
async def me(user: User = Depends(get_current_user)) -> UserResponse:
    return _user_response(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    payload: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    user = await user_service.update_user(
        db, current_user.id, **payload.model_dump(exclude_unset=True)
    )
    invalidate_user(user.id)
    return _user_response(user)


@router.delete("/me", status_code=status.HTTP_200_OK)
async def delete_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    await user_service.delete_user(db, current_user.id)
    invalidate_user(current_user.id)
    return {"detail": "Account deleted successfully"}


@router.get("/my-project-roles", response_model=MyProjectRolesResponse)
async def my_project_roles(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyProjectRolesResponse:
    roles = await list_user_project_roles(db, user.id)
    return MyProjectRolesResponse(
        is_platform_admin=user.is_platform_admin,
        project_roles=roles,
    )


@router.get("/my-roles", response_model=list[MyRoleResponse])
async def my_roles(
    app_key: str | None = Query(default=None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MyRoleResponse]:
    roles = await authorization_service.list_roles(db, user.id, app_key)
    return [MyRoleResponse(app_key=entry[0], role_key=entry[1]) for entry in roles]


@router.get("/my-managed-orgs", response_model=MyManagedOrgsResponse)
async def my_managed_orgs(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyManagedOrgsResponse:
    org_ids = await get_managed_org_ids(db, user.id)
    return MyManagedOrgsResponse(managed_org_ids=org_ids)


@router.post("/forgot-password", response_model=PasswordResetResponse)
async def forgot_password(
    payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)
) -> PasswordResetResponse:
    await auth_service.request_password_reset(db, payload.email, payload.app_key)
    return PasswordResetResponse(message="If an account exists, a reset link has been sent.")


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)
) -> PasswordResetResponse:
    await auth_service.reset_password_with_token(db, payload.token, payload.password)
    return PasswordResetResponse(message="Password has been reset successfully.")
