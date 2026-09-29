from datetime import UTC, datetime
from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.resource_request import RRRequestLink
from app.models.resource_request import LinkStatus
from app.services.common import tokens
from app.services.resource_request._links import link_status


class PublicLink(NamedTuple):
    status: LinkStatus
    email_hint: str
    project_hint: str
    expires_at: datetime


def mask_email(email: str) -> str:
    """``e***@fora.org`` — enough for the holder to recognise their address, not to learn one."""
    local, _, domain = email.partition("@")
    return f"{local[:1]}***@{domain}" if domain else "***"


async def find_link(db: AsyncSession, raw_token: str) -> RRRequestLink:
    """The link a raw token names, looked up by its digest, or 404."""
    row = await db.execute(
        select(RRRequestLink).where(RRRequestLink.token_hash == tokens.digest(raw_token))
    )
    link = row.scalar_one_or_none()
    if link is None:
        raise NotFoundError("Request link not found")
    return link


async def read_request_link(db: AsyncSession, raw_token: str) -> PublicLink:
    """What the public screen shows before the code — BE-26 (OBT-537), PR B.

    **A known link's state is read, never refused**, so the screen can say *expired* or
    *revoked* instead of a bare error: the holder did nothing wrong by opening an old e-mail.
    An unknown token is 404. The address is masked; the full one is the Admin's to read.
    """
    link = await find_link(db, raw_token)
    return PublicLink(
        status=link_status(link, datetime.now(UTC)),
        email_hint=mask_email(link.email),
        project_hint=link.project_hint,
        expires_at=link.expires_at,
    )
