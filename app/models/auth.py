from datetime import datetime
from typing import Any, Final

from pydantic import BaseModel, EmailStr, Field

#: The most a handoff's ``context`` may weigh, as compact UTF-8 JSON. The PME sends
#: ``{"projectId": …}``, a few dozen bytes; a kilobyte leaves room for a few more ids and none
#: for a document, which is what a column nobody reads must not become.
HANDOFF_CONTEXT_MAX_BYTES: Final = 1024

#: The three refusals of a handoff exchange, each its own ``code`` so the receiving app can
#: say which happened and offer the way back (OBT-538). The same shape as the claim-code
#: triple in ``app/models/device.py``; a code the server never issued, one past its minute
#: and one already spent ask the person for the same thing — go back and ask again — but
#: *already spent* is also the sign that somebody else may have used it.
ERROR_CODE_HANDOFF_CODE_UNKNOWN: Final = "HANDOFF_CODE_UNKNOWN"
ERROR_CODE_HANDOFF_CODE_EXPIRED: Final = "HANDOFF_CODE_EXPIRED"
ERROR_CODE_HANDOFF_CODE_USED: Final = "HANDOFF_CODE_USED"


class UserSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=120)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class TokenRefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str | None
    avatar_url: str | None = None
    is_active: bool
    is_platform_admin: bool
    locale: str | None = None


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    avatar_url: str | None = None
    locale: str | None = Field(default=None, max_length=10)


class AuthResponse(BaseModel):
    user: UserResponse
    tokens: TokenResponse


class MyProjectRolesResponse(BaseModel):
    is_platform_admin: bool
    project_roles: dict[str, str]


class MyManagedOrgsResponse(BaseModel):
    managed_org_ids: list[str]


class MyManagedProjectsResponse(BaseModel):
    managed_project_ids: list[str]


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    app_key: str = Field(max_length=100)


class ResetPasswordRequest(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class PasswordResetResponse(BaseModel):
    message: str


class HandoffRequest(BaseModel):
    """Ask for a code that opens ``app_key`` signed in as the caller (BE-21).

    ``refresh_token`` is the caller's own session, and it is what makes *a valid session* a
    fact the server can check: the bearer token is stateless for thirty minutes, so without
    it an access token that leaked would mint a fresh seven-day session, and go on minting
    after a logout or a password reset had revoked everything else.

    ``context`` is opaque to the server and handed back as it came: a JSON object, because
    both of its consumers read named keys. Its weight and its numbers are checked by
    ``create_handoff`` and not here, for a reason that is FastAPI's: a refusal raised by this
    model is answered with the offending input echoed back, and a ``NaN`` in that echo cannot
    be serialised — the 422 would itself fail as a 500.
    """

    app_key: str = Field(min_length=1, max_length=100)
    refresh_token: str
    context: dict[str, Any] | None = None


class HandoffResponse(BaseModel):
    """The only copy of the code there will ever be, and the moment it dies."""

    code: str
    expires_at: datetime


class HandoffExchangeRequest(BaseModel):
    code: str


class HandoffExchangeResponse(AuthResponse):
    """What login answers, plus the ``context`` the asking app sent — untouched."""

    context: dict[str, Any] | None
