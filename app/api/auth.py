import ipaddress
from collections.abc import Mapping
from typing import Final

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cache import invalidate_user
from app.core.auth_middleware import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.core.org_scope import get_managed_org_ids, get_managed_project_ids
from app.core.rate_limit import limiter
from app.db.models.auth import User
from app.models.auth import (
    ERROR_CODE_HANDOFF_CODE_EXPIRED,
    ERROR_CODE_HANDOFF_CODE_UNKNOWN,
    ERROR_CODE_HANDOFF_CODE_USED,
    AuthResponse,
    ForgotPasswordRequest,
    HandoffExchangeRequest,
    HandoffExchangeResponse,
    HandoffRequest,
    HandoffResponse,
    MyManagedOrgsResponse,
    MyManagedProjectsResponse,
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
from app.services.auth.exchange_handoff import HandoffRefusal, HandoffRefused
from app.services.project import list_user_project_roles

router = APIRouter()

#: How often one address may try to exchange a handoff code —
#: ``auth_handoff_exchange_limit_per_minute``, read once at import.
HANDOFF_EXCHANGE_RATE_LIMIT: Final = (
    f"{get_settings().auth_handoff_exchange_limit_per_minute}/minute"
)

#: Keyed by the service's reason. A reason not listed here falls to the unknown answer, so a
#: refusal nobody mapped never invents a ``code`` of its own.
_HANDOFF_REFUSALS: Mapping[HandoffRefusal, tuple[str, str]] = {
    "expired": ("This handoff code has expired.", ERROR_CODE_HANDOFF_CODE_EXPIRED),
    "used": ("This handoff code has already been used.", ERROR_CODE_HANDOFF_CODE_USED),
}
_UNKNOWN_HANDOFF = ("This handoff code is not valid.", ERROR_CODE_HANDOFF_CODE_UNKNOWN)


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
        db, current_user.id, current_user, **payload.model_dump(exclude_unset=True)
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


@router.get("/my-managed-projects", response_model=MyManagedProjectsResponse)
async def my_managed_projects(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MyManagedProjectsResponse:
    project_ids = await get_managed_project_ids(db, user.id)
    return MyManagedProjectsResponse(managed_project_ids=project_ids)


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


def _client_address(request: Request) -> str | None:
    """The address the handoff was asked from, if it reads as one — otherwise nothing.

    ``request.client`` rather than ``get_remote_address``, which answers ``127.0.0.1`` when
    there is no client and would store an address nobody used. Behind
    ``ProxyHeadersMiddleware(trusted_hosts="*")`` the host is the first ``X-Forwarded-For``
    entry, which the caller writes, so it is parsed rather than trusted: an IPv6 zone is
    dropped, and anything that is not an address is stored as NULL instead of reaching a
    45-character column as whatever the header carried.
    """
    if request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host.split("%", 1)[0]))
    except ValueError:
        return None


@router.post("/handoff", response_model=HandoffResponse, status_code=status.HTTP_201_CREATED)
async def handoff(
    payload: HandoffRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> HandoffResponse:
    """A one-minute, single-use code that opens ``app_key`` signed in as the caller (BE-21).

    Not the JWT itself in the other app's URL: an access token lives thirty minutes and a
    refresh token seven days, and either one in a URL leaks through history, proxy logs and
    ``Referer``. The asking app puts this code in the URL **fragment**, which the browser
    sends to no server, and the other app trades it through ``/handoff/exchange``. The body
    carries the session's own refresh token, which is what lets a logout or a password reset
    close this door too — ``create_handoff`` has the argument.
    """
    return await auth_service.create_handoff(
        db,
        user,
        app_key=payload.app_key,
        refresh_token=payload.refresh_token,
        context=payload.context,
        created_ip=_client_address(request),
    )


@router.post("/handoff/exchange", response_model=HandoffExchangeResponse)
@limiter.limit(HANDOFF_EXCHANGE_RATE_LIMIT, key_func=get_remote_address)
async def exchange_handoff(
    payload: HandoffExchangeRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> HandoffExchangeResponse | JSONResponse:
    """Trade a handoff code for the session login would have issued, and its ``context``.

    Public: the code is the credential. Counted per address and per this path — slowapi's
    bucket is the address and the URL, so the code travels in the body and must stay there,
    or it would become part of every bucket key. The 256 bits of the code are what guard it;
    behind a proxy that trusts every ``X-Forwarded-For``, the address is one a caller can
    change, so this limit is a toll on guessing and not a ceiling.

    The three refusals answer 401 with a ``code`` each, so the receiving app can say which
    happened and send the person back to where they came from.
    """
    try:
        exchanged = await auth_service.exchange_handoff(db, payload.code)
    except HandoffRefused as refused:
        detail, code = _HANDOFF_REFUSALS.get(refused.reason, _UNKNOWN_HANDOFF)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail, "code": code},
        )
    return HandoffExchangeResponse(
        user=_user_response(exchanged.user),
        tokens=TokenResponse(
            access_token=exchanged.access_token, refresh_token=exchanged.refresh_token
        ),
        context=exchanged.context,
    )
