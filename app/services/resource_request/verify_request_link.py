import hmac
from datetime import UTC, datetime
from typing import Final, Literal, NamedTuple

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RRRequestLink
from app.services.common import tokens
from app.services.resource_request._links import link_status
from app.services.resource_request.link_session import encode_link_session
from app.services.resource_request.read_request_link import find_link
from app.utils.stored_time import as_utc

#: The fifth wrong code revokes the link — the issue's number.
MAX_CODE_ATTEMPTS: Final = 5


class Verified(NamedTuple):
    session: str
    expires_at: datetime
    #: The link's address, whole — whoever typed the code sent to it has just proved it is theirs
    #: (FE-55, OBT-542). The form needs it for *"solicitante nunca endossa"*: the masked hint of
    #: the public read never equals a real address, so a check against it could never fire.
    email: str


class Refused(NamedTuple):
    #: ``wrong_code`` — try again, ``attempts_left`` more; ``gone`` — expired or revoked,
    #: including by this very attempt.
    reason: Literal["wrong_code", "gone"]
    attempts_left: int


async def verify_request_link(db: AsyncSession, raw_token: str, code: str) -> Verified | Refused:
    """Trade the link's code for a link session — BE-26 (OBT-537), PR B.

    * An unknown token is 404 (``find_link``).
    * An expired or revoked link is ``gone``: the session would die at once, and saying so is
      kinder than a code that seems wrong.
    * **A wrong code counts, and the fifth revokes.** The count is a guarded ``UPDATE … SET
      code_attempts = code_attempts + 1``, so two wrong codes at once are two, never one — the
      argument ``exchange_handoff`` makes for its spend. What protects a six-digit code is its
      attempt limit (BE-20's ``mint_code`` says so), so the limit must not be raceable.
    * The right code marks the first ``verified_at``, **zeroes the count** and answers a
      session. A link is multi-use: verifying again, from another phone, is legitimate — and a
      phone that mistyped four times before getting it right must not leave the link one try
      from revocation for everyone else. The five stop a guesser, who never gets it right
      (PR #577, review).
    * **The session never outlives the link**: its expiry is the earlier of thirty days and the
      link's own ``expires_at``, so the date the screen shows is one the session reaches.

    The code is compared by digest and in constant time.
    """
    link = await find_link(db, raw_token)
    now = datetime.now(UTC)
    if link_status(link, now) in ("expired", "revoked"):
        return Refused(reason="gone", attempts_left=0)

    if not hmac.compare_digest(tokens.digest(code.strip()), link.code_hash):
        counted = await db.execute(
            update(RRRequestLink)
            .where(RRRequestLink.id == link.id)
            .values(code_attempts=RRRequestLink.code_attempts + 1)
            .returning(RRRequestLink.code_attempts)
        )
        attempts = counted.scalar_one()
        if attempts >= MAX_CODE_ATTEMPTS:
            await db.execute(
                update(RRRequestLink)
                .where(RRRequestLink.id == link.id, RRRequestLink.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await db.commit()
            return Refused(reason="gone", attempts_left=0)
        await db.commit()
        return Refused(reason="wrong_code", attempts_left=MAX_CODE_ATTEMPTS - attempts)

    link.verified_at = link.verified_at or now
    link.code_attempts = 0
    await db.commit()
    session, expires_at = encode_link_session(link.id, now, not_after=as_utc(link.expires_at))
    return Verified(session=session, expires_at=expires_at, email=link.email)
