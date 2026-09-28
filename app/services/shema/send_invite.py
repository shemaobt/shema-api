"""``POST /access/invites`` — the Admin invites somebody without an account.

The invitation itself is the form's invite module (``invite_store``), behind this surface's
own rules: a role the surface grants, never ``admin`` by link, a regional role with its
regions — stored on the invite and applied when it is accepted.

**Every link lands on the PME**, ``{shema app_url}/convite?token=…``, whichever app the role
lives in. The form has had no sign-in since 22/set, so a Gestor or a mesa invited here signs
up and accepts in the PME too; ``/convite`` is the page OBT-546 builds. The letter is BE-12's
``access_invite`` template, named after the app the person is joining. It leaves after the
row is committed and is best-effort, and the answer says whether it left, beside the link
the Admin can hand over another way.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RoleError
from app.db.models.auth import User
from app.models.shema_grant import InviteRequest, SentInvite
from app.services.authorization.get_app_by_key import get_app_by_key
from app.services.common.email import send_access_invite_email
from app.services.resource_request_access.invite_store import (
    InviteRow,
    invite_link,
    issue_invite,
)
from app.services.shema._grant_rules import (
    GrantApps,
    refuse_admin_by_link,
    require_admin_in,
    require_grantable,
    require_regions,
)
from app.services.shema.list_invites import open_invite

#: The PME's page an invitation opens — OBT-546's ``/convite?token=``.
INVITE_PAGE = "convite"


async def send_invite(
    db: AsyncSession, apps: GrantApps, *, payload: InviteRequest, actor: User
) -> SentInvite:
    """Write the invitation, mail its link, and answer the link once."""
    role_key = payload.role_key
    require_grantable(apps, payload.app_key, role_key)
    refuse_admin_by_link(role_key)
    regions = require_regions(role_key, (key.value for key in payload.region_keys))
    await require_admin_in(db, actor, (payload.app_key,))
    landing = await get_app_by_key(db, apps.shema)
    if landing is None:
        raise RoleError("App not found")

    issued = await issue_invite(
        db, actor, payload.app_key, str(payload.email), role_key, region_keys=regions
    )
    url = invite_link(landing, issued.raw_token, page=INVITE_PAGE)
    sent = await send_access_invite_email(
        to_email=issued.invite.email,
        inviter_name=actor.display_name,
        invite_url=url,
        app_name=landing.name,
    )
    entry = open_invite(InviteRow(issued.invite, issued.app.app_key, issued.role.role_key))
    return SentInvite.model_validate(
        {**entry.model_dump(by_alias=True), "inviteUrl": url, "emailSent": sent}
    )
