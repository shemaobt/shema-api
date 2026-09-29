from datetime import UTC, datetime
from typing import Any, Literal, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RREndorsementLink, RRRequest, RRSnapshot
from app.services.resource_request._endorsement import endorsement_status, find_endorsement
from app.services.resource_request._notices import request_name
from app.services.resource_request.read_request_link import mask_email

EndorsementState = Literal["pending", "verified", "endorsed", "expired", "revoked"]


class PublicEndorsement(NamedTuple):
    status: EndorsementState
    email_hint: str
    request_name: str
    expires_at: datetime
    #: The request as it was submitted — only once the code was confirmed, and never after
    #: the link expired or was revoked, endorsed or not.
    document: dict[str, Any] | None


async def read_endorsement(db: AsyncSession, raw_token: str) -> PublicEndorsement:
    """What the leader's page shows — BE-23 (OBT-535).

    **The state is read, never refused**, so the page can say *expired* or *revoked* rather
    than a bare error; an unknown token is 404. The request's name is shown before the code:
    the letter already named it to this address.

    **The document is the frozen one**, the latest snapshot — what the team submitted and the
    leader signs. It carries Parts A and B and no evaluation, which lives in its own aggregate
    and never reaches this path. There is nothing to redact beyond that: the form asks no
    country and no base, and what the team typed is exactly what the leader attests.
    """
    link = await find_endorsement(db, raw_token)
    request = await db.get(RRRequest, link.request_id)
    assert request is not None
    alive = endorsement_status(link, datetime.now(UTC)) in ("pending", "used")
    state = _state(link, alive)
    return PublicEndorsement(
        status=state,
        email_hint=mask_email(link.email),
        request_name=request_name(request),
        expires_at=link.expires_at,
        document=await _frozen(db, request.id) if alive and link.verified_at else None,
    )


def _state(link: RREndorsementLink, alive: bool) -> EndorsementState:
    """**An endorsed link reads ``endorsed`` for good** — the invite's order, *used* before
    *expired*, because this link is spent by one act (PR #579, review). The token module reads
    the multi-use order, ``expired`` first, and would answer *expired* on day 15 for a request
    that is endorsed; the fact outlives the link. **The document does not**: it is served only
    while the link is alive, so the leader rereads what was signed for fourteen days and not
    for as long as an old e-mail survives. *Endorsed* is read even before *revoked*: five wrong
    codes on a spent link revoke it, and they do not undo the endorsement."""
    if link.used_at is not None:
        return "endorsed"
    if link.revoked_at is not None:
        return "revoked"
    if not alive:
        return "expired"
    return "verified" if link.verified_at is not None else "pending"


async def _frozen(db: AsyncSession, request_id: str) -> dict[str, Any] | None:
    snapshot = (
        await db.execute(
            select(RRSnapshot.document)
            .where(RRSnapshot.request_id == request_id)
            .order_by(RRSnapshot.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    return dict(snapshot) if snapshot is not None else None
