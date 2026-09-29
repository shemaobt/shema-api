from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, ConflictError
from app.db.models.resource_request import RREndorsementLink, RRRequest
from app.services.resource_request._endorsement import endorsement_status, find_endorsement


async def endorse_by_link(
    db: AsyncSession, raw_token: str, leader_name: str
) -> RRRequest | Literal["gone"]:
    """The base leader's act, through the link submission mailed — BE-23 (OBT-535).

    GATE-02 D2 described it — *"tipo uma caixinha pra ele assinalar e confirmar que o projeto
    realmente pertence à base dele"* — and the 22/set meeting took the leader's account away:
    the link is the leader. So the stamp is the link's: ``endorsed_email`` is its address,
    ``endorsement_link_id`` the link, ``endorsed_at`` and ``leader_date`` the moment, and
    ``leader_name`` the one thing typed — a name, since the leader has no account to read one
    from. ``endorsed_by`` is not written: there is no account behind the act.

    Refused, each for its own reason:

    * **expired or revoked** — answered as ``"gone"``, which the route makes a 410, as the
      code's verification does;
    * **not verified** — the code is what proves the address, and the token alone is a URL that
      may have travelled;
    * **twice** — a signature is not a value to update, and read before the clock, so a second
      try on day 15 is told the request is endorsed rather than that the link is gone. The
      spend is a guarded ``UPDATE … WHERE used_at IS NULL``, so two endorsements at once are
      one, and the loser is told;
    * **a request already endorsed** — by an older link, or by a BE-16 account before the
      change.

    **The snapshot keeps the document as submitted** (BE-16's reasoning, unchanged): the
    endorsement is a fact that can only exist after the freeze, and the envelope is where it
    lives. Nothing here moves the card: ``guard_endorsement`` reads ``endorsed_at`` when the
    mesa moves it.
    """
    link = await find_endorsement(db, raw_token)
    now = datetime.now(UTC)
    if link.used_at is not None:
        raise ConflictError("This request was already endorsed through this link.")
    if endorsement_status(link, now) in ("expired", "revoked"):
        return "gone"
    if link.verified_at is None:
        raise AuthorizationError("Confirm the code sent with this link before endorsing.")

    request = await db.get(RRRequest, link.request_id)
    assert request is not None
    if request.endorsed_at is not None:
        raise ConflictError("This request was already endorsed.")

    spent = await db.execute(
        update(RREndorsementLink)
        .where(RREndorsementLink.id == link.id, RREndorsementLink.used_at.is_(None))
        .values(used_at=now)
    )
    if spent.rowcount != 1:
        await db.rollback()
        raise ConflictError("This request was already endorsed through this link.")

    request.endorsed_at = now
    request.endorsed_email = link.email
    request.endorsement_link_id = link.id
    request.leader_name = leader_name.strip()
    request.leader_date = now.date()
    await db.commit()
    await db.refresh(request)
    return request
