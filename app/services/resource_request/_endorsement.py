"""The base leader's endorsement link: issued at submission, read by its token — BE-23 (OBT-535).

**The leader has no account** (OBT-522, 22/set). The team types the leader's address in the draft
(``leader_email``), and **submitting** issues a link tied to the request and a six-digit code,
mailed to that address. Daniel, 25/set: *"o link só pode ficar disponível após todo o forms ser
preenchido"* — so the link is born with the submission and never before it.

**A link's state is the token module's** (BE-20), with ``used_at`` as its *used*: the endorsement
spends the link, and a spent link reads as ``used`` even before its clock runs out.
``verified_at`` is not a state — it is the permission to read and to endorse.

**The letter leaves after the caller's commit**, like every letter of this module (BE-12): a
provider outage never un-submits a request. With no ``app_url`` in the registry no letter
leaves, and the Admin's resend is how a link reaches the leader then.
"""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.db.models.auth import App
from app.db.models.resource_request import RREndorsementLink, RRRequest
from app.services.common import tokens
from app.services.notifications.get_rr_app_id import get_rr_app_id
from app.services.resource_request._notices import Letter, letter, request_name

ENDORSEMENT_TITLE = "A request is waiting for your endorsement"


def endorsement_status(link: RREndorsementLink, now: datetime) -> tokens.TokenStatus:
    return tokens.status(link, now)


async def issue_endorsement(db: AsyncSession, request: RRRequest) -> Letter | None:
    """Mint the link and the code for ``request``, and answer the letter that carries them.

    Revokes the live link first, so the one-live index holds for the Admin's resend and for a
    first submission alike. Adds rows and never commits: the caller's transaction carries the
    link with the act that issued it.
    """
    now = datetime.now(UTC)
    await db.execute(
        update(RREndorsementLink)
        .where(
            RREndorsementLink.request_id == request.id,
            RREndorsementLink.used_at.is_(None),
            RREndorsementLink.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    token = tokens.mint()
    code = tokens.mint_code()
    link = RREndorsementLink(
        request_id=request.id,
        email=request.leader_email,
        token_hash=token.digest,
        code_hash=code.digest,
        expires_at=tokens.expiry(now, days=get_settings().rr_endorsement_link_expire_days),
    )
    db.add(link)
    await db.flush()
    return await _letter(db, request, link, token.raw, code.raw)


async def _letter(
    db: AsyncSession, request: RRRequest, link: RREndorsementLink, token: str, code: str
) -> Letter | None:
    """The URL is the form's ``app_url`` plus ``/endossar/{token}`` — the page FE-54 (OBT-540)
    builds, not this API's route."""
    app = await db.get(App, await get_rr_app_id(db))
    if app is None or not app.app_url:
        return None
    return letter(
        to=link.email,
        subject=ENDORSEMENT_TITLE,
        template="rr_endorsement.html.jinja",
        app_name=app.name,
        url=f"{app.app_url.rstrip('/')}/endossar/{token}",
        code=code,
        request_name=request_name(request),
        expires=link.expires_at.strftime("%d/%m/%Y"),
    )


async def find_endorsement(db: AsyncSession, raw_token: str) -> RREndorsementLink:
    """The link a raw token names, looked up by its digest, or 404."""
    row = await db.execute(
        select(RREndorsementLink).where(RREndorsementLink.token_hash == tokens.digest(raw_token))
    )
    link = row.scalar_one_or_none()
    if link is None:
        raise NotFoundError("Endorsement link not found")
    return link
