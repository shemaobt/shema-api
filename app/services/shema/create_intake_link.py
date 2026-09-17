"""Minting one leader link — the one place this module issues a credential to a non-user.

Everything the link is, is decided in the two files under it: ``_intake_tokens.py`` holds the
token, the expiry and the revocation, and ``_form_definitions.py`` publishes and pins the
version. What is decided *here* is the one thing neither of them can see — **that the
coordinator minting it may reach the project**, checked through ``visible_projects`` exactly as
a read is, so a link cannot be minted for a region the minter cannot see.

**The definition is published and pinned in the same transaction as the link.** A link
pointing at a version that rolled back would serve a form nobody published; a version
published without its link would cut a version for nothing. One commit under both.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema import ShemaProject
from app.db.models.shema_form import ShemaIntakeLink
from app.models.shema_forms import IntakeLinkCreate, IntakeLinkCreated
from app.services import authorization_service
from app.services.shema._form_definitions import publish_definition
from app.services.shema._intake_tokens import (
    expires_on,
    expiry_from,
    intake_url,
    link_status,
    mint_token,
)
from app.services.shema._scope import RegionScope, refuse_out_of_scope, visible_projects
from app.utils.shema_forms import PULSE_KIND
from app.utils.stored_time import as_utc


async def create_intake_link(
    db: AsyncSession,
    scope: RegionScope,
    payload: IntakeLinkCreate,
    *,
    user: User,
    app_key: str,
    today: date,
) -> IntakeLinkCreated:
    """Issue a link for one project, and hand back the only copy of its token.

    The raw token is in the response and in nothing else — not in the row, not in the log, not
    in a later listing. That is what every token in this repository does, and this one has the
    strongest case for it: its holder has no account, so a database dump is the only place it
    could ever be read from.
    """
    project = (
        await db.execute(visible_projects(scope).where(ShemaProject.id == payload.project_id))
    ).scalar_one_or_none()
    if project is None:
        raise refuse_out_of_scope(
            scope, user=user, operation="create_intake_link", project_id=payload.project_id
        )

    definition = await publish_definition(db, PULSE_KIND)
    raw_token, token_hash = mint_token()
    link = ShemaIntakeLink(
        project_id=project.id,
        token_hash=token_hash,
        created_by=user.id,
        definition_id=definition.id,
        expires_at=expiry_from(payload.expires_at, today=today),
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    app = await authorization_service.get_app_by_key(db, app_key)
    return IntakeLinkCreated(
        id=link.id,
        project_id=link.project_id,
        definition_version=definition.version,
        expires_at=expires_on(link),
        status=link_status(link),
        created_at=as_utc(link.created_at).date(),
        used_at=None,
        revoked_at=None,
        token=raw_token,
        url=intake_url(None if app is None else app.app_url, raw_token),
    )
