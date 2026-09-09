"""Request/response shapes for the privileged-access surface (OBT-477).

``InviteStatus`` is one word on purpose: it is what FE-30's screen switches on,
and what the public lookup answers so the front can route a link-holder to
signup or login without guessing.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr

InviteStatus = Literal["pending", "expired", "used", "revoked"]


class AccessGrantRequest(BaseModel):
    target_user_id: str
    role_key: str


class AccessRevokeRequest(BaseModel):
    target_user_id: str
    role_key: str


class AccessGrantResponse(BaseModel):
    user_id: str
    role_key: str
    granted_at: datetime
    granted_by: str | None
    revoked_at: datetime | None
    revoked_by: str | None


class AccessAssignmentResponse(BaseModel):
    user_id: str
    email: str | None
    display_name: str | None
    role_key: str
    granted_at: datetime
    granted_by: str | None
    revoked_at: datetime | None
    revoked_by: str | None


class InviteCreateRequest(BaseModel):
    email: EmailStr
    role_key: str


class InviteResponse(BaseModel):
    id: str
    email: str
    role_key: str
    status: InviteStatus
    created_at: datetime
    expires_at: datetime
    created_by: str | None


class InviteCreatedResponse(InviteResponse):
    """The creator's copy also carries the link, so a lost e-mail is recoverable."""

    invite_url: str


class InviteRevokeRequest(BaseModel):
    invite_id: str


class InviteDescriptionResponse(BaseModel):
    """What the public lookup tells an anonymous link-holder — and nothing more."""

    status: InviteStatus
    email: str
    app_name: str
    role_key: str
    role_label: str
    account_exists: bool


class AccessOverviewResponse(BaseModel):
    """FE-30's screen in one call: who holds what, and which doors are ajar."""

    grants: list[AccessAssignmentResponse]
    invites: list[InviteResponse]
