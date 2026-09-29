from datetime import UTC, datetime
from typing import Any, Literal, NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequest, RRSnapshot
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
    #: the link expired or was revoked.
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
    state = _state(endorsement_status(link, datetime.now(UTC)), link.verified_at is not None)
    return PublicEndorsement(
        status=state,
        email_hint=mask_email(link.email),
        request_name=request_name(request),
        expires_at=link.expires_at,
        document=await _frozen(db, request.id) if state in ("verified", "endorsed") else None,
    )


def _state(token_state: str, verified: bool) -> EndorsementState:
    if token_state == "used":
        return "endorsed"
    if token_state == "pending":
        return "verified" if verified else "pending"
    return "expired" if token_state == "expired" else "revoked"


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
