from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.auth import User
from app.db.models.resource_request import RRRequestLink
from app.services.common import tokens
from app.services.resource_request._links import require_link_admin
from app.services.resource_request._notices import post
from app.services.resource_request.notify_link import link_letter


class IssuedLink(NamedTuple):
    link: RRRequestLink
    #: The raw token and code, returned **once** — only their digests are stored.
    token: str
    code: str


async def create_request_link(
    db: AsyncSession,
    email: str,
    project_hint: str,
    user: User,
    app_key: str,
    shema_app_key: str,
) -> IssuedLink:
    """Issue a request link to ``email`` — BE-26 (OBT-537), the Admin alone.

    Two secrets are minted, and neither is kept: the **token** the link's URL carries and the
    six-digit **code** verification asks for (``tokens.mint`` and ``tokens.mint_code``, BE-20).
    Both leave in this answer and in one e-mail to the address (``notify_link.link_letter``),
    posted after the commit — best-effort, as every letter of this module is, so a provider
    outage never un-issues a link; the Admin's answer still carries both. The
    code is what makes the URL alone not enough — a link seen in a log, a ``Referer`` or a
    screenshot opens nothing without it — and five wrong codes revoke the link (PR B).

    **The address is stored lower-cased**, because it is compared later against the leader's
    e-mail, which may not be the requester's own (the issue's DoD) — and two spellings of one
    address must not pass that comparison.
    """
    await require_link_admin(db, user, app_key, shema_app_key)

    token = tokens.mint()
    code = tokens.mint_code()
    now = datetime.now(UTC)
    link = RRRequestLink(
        email=email.strip().lower(),
        token_hash=token.digest,
        code_hash=code.digest,
        project_hint=project_hint.strip(),
        expires_at=tokens.expiry(now, days=get_settings().rr_request_link_expire_days),
        created_by=user.id,
    )
    db.add(link)
    await db.commit()
    await db.refresh(link)

    delivery = await link_letter(db, link, token.raw, code.raw)
    if delivery is not None:
        await post([delivery])
    return IssuedLink(link=link, token=token.raw, code=code.raw)
