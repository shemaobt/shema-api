"""The Admin's surface on the wire — ``/api/shema/access`` (OBT-543).

camelCase by alias over the house's snake_case attributes, ``app/models/shema_session.py``'s
mechanism, because the PME's console is the reader. Requests forbid unknown keys, so a
misspelt ``regionkeys`` is refused rather than read as *no regions*.

**Role keys are ``str`` and not a ``Literal``**, for the session model's reason: the
vocabulary's owner is ``app/services/shema/_grant_rules.py``, which a DTO module may not
import (``tests/test_app_boots.py``), and a second spelling of it here is the drift the one
owner exists to prevent. Region keys *are* typed — ``ShemaRegionKey`` is a frozen vocabulary
of seven the console already holds — so an unknown one is FastAPI's 422 before any service
runs.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models.shema_enums import ShemaRegionKey
from app.models.resource_request_access import InviteStatus

_REQUEST = ConfigDict(populate_by_name=True, extra="forbid")
_RESPONSE = ConfigDict(populate_by_name=True)


class AppRoles(BaseModel):
    """The roles an account holds in one app, among those the surface writes."""

    model_config = _RESPONSE

    app_key: str = Field(alias="appKey")
    roles: list[str] = Field(default_factory=list)


class RegionGrant(BaseModel):
    """One stored region of an account's scope: who granted it, and when."""

    model_config = _RESPONSE

    region_key: str = Field(alias="regionKey")
    granted_by: str | None = Field(default=None, alias="grantedBy")
    granted_at: datetime = Field(alias="grantedAt")


class AccountGrants(BaseModel):
    """One account as the Admin sees it — what the lookup, a grant and a revocation answer.

    ``regions`` are the stored rows the Admin edits; ``regionScope`` is what they reach, by
    the session's own rule (``null`` = every region). The two differ for rows left under no
    regional role, which reach nothing.
    """

    model_config = _RESPONSE

    user_id: str = Field(alias="userId")
    email: str
    display_name: str | None = Field(default=None, alias="displayName")
    is_active: bool = Field(alias="isActive")
    apps: list[AppRoles]
    regions: list[RegionGrant]
    region_scope: list[str] | None = Field(default=None, alias="regionScope")


class RoleGrantRequest(BaseModel):
    """``POST /access/grants``. ``regionKeys`` is the account's whole scope, not an addition."""

    model_config = _REQUEST

    user_id: str = Field(alias="userId")
    app_key: str = Field(alias="appKey")
    role_key: str = Field(alias="roleKey")
    region_keys: list[ShemaRegionKey] = Field(default_factory=list, alias="regionKeys")


class RoleRevokeRequest(BaseModel):
    """``POST /access/grants/revoke``."""

    model_config = _REQUEST

    user_id: str = Field(alias="userId")
    app_key: str = Field(alias="appKey")
    role_key: str = Field(alias="roleKey")


class InviteRequest(BaseModel):
    """``POST /access/invites``."""

    model_config = _REQUEST

    email: EmailStr
    app_key: str = Field(alias="appKey")
    role_key: str = Field(alias="roleKey")
    region_keys: list[ShemaRegionKey] = Field(default_factory=list, alias="regionKeys")


class InviteWithdrawRequest(BaseModel):
    """``POST /access/invites/revoke``."""

    model_config = _REQUEST

    invite_id: str = Field(alias="inviteId")


class OpenInvite(BaseModel):
    """An invite nobody accepted yet, with the state ``_invite_status`` reads off it."""

    model_config = _RESPONSE

    id: str
    email: str
    app_key: str = Field(alias="appKey")
    role_key: str = Field(alias="roleKey")
    region_keys: list[str] = Field(default_factory=list, alias="regionKeys")
    status: InviteStatus
    created_at: datetime = Field(alias="createdAt")
    expires_at: datetime = Field(alias="expiresAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    #: The team an invitation to a project's team puts somebody on (OBT-547), whose
    #: ``roleKey`` then reads ``equipe``; ``null`` for every invitation to a role.
    project_id: str | None = Field(default=None, alias="projectId")


class SentInvite(OpenInvite):
    """The creator's copy: the link, shown once, and whether the letter left.

    ``emailSent`` false means the provider refused and the row still stands — the link is the
    way to hand the invitation over.
    """

    invite_url: str = Field(alias="inviteUrl")
    email_sent: bool = Field(alias="emailSent")


class GrantChange(BaseModel):
    """One entry of the history: a role or a region, granted or revoked, by whom and when.

    Exactly one of ``roleKey`` and ``regionKey`` is set. A region entry's ``appKey`` is the
    Shemá app, whose scope it is. ``actor*`` are ``null`` when nobody acted — an automatic
    grant — or when that account no longer exists.
    """

    model_config = _RESPONSE

    action: Literal["granted", "revoked"]
    at: datetime
    app_key: str = Field(alias="appKey")
    role_key: str | None = Field(default=None, alias="roleKey")
    region_key: str | None = Field(default=None, alias="regionKey")
    user_id: str = Field(alias="userId")
    user_email: str | None = Field(default=None, alias="userEmail")
    user_name: str | None = Field(default=None, alias="userName")
    actor_id: str | None = Field(default=None, alias="actorId")
    actor_email: str | None = Field(default=None, alias="actorEmail")
    actor_name: str | None = Field(default=None, alias="actorName")
