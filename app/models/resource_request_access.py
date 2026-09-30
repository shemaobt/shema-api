"""Response shapes for the invite doors the PME's ``/convite`` page still calls (OBT-477).

FE-56 (OBT-549) retired the form's own access screen and, with it, the request shapes of
naming, revoking and issuing invites here: roles are granted in the PME now, by the Admin
alone (OBT-522). What stays is what an anonymous link-holder is answered and what accepting
returns.

``InviteStatus`` is one word on purpose: it is what the public lookup answers so the front can
route a link-holder to signup or login without guessing.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

InviteStatus = Literal["pending", "expired", "used", "revoked"]


class AccessGrantResponse(BaseModel):
    user_id: str
    role_key: str
    granted_at: datetime
    granted_by: str | None
    revoked_at: datetime | None
    revoked_by: str | None


class InviteDescriptionResponse(BaseModel):
    """What the public lookup tells an anonymous link-holder — and nothing more."""

    status: InviteStatus
    email: str
    app_name: str
    role_key: str
    role_label: str
    account_exists: bool
    #: The region scope a regional Shemá invite applies on acceptance; empty otherwise.
    region_keys: list[str] = []
