import hmac
from datetime import UTC, datetime
from typing import Final, Literal, NamedTuple

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.resource_request import RREndorsementLink
from app.services.common import tokens
from app.services.resource_request._endorsement import endorsement_status, find_endorsement

#: The fifth wrong code revokes the link — the issue's number, and the request link's.
MAX_ENDORSEMENT_ATTEMPTS: Final = 5


class CodeRefused(NamedTuple):
    #: ``wrong_code`` — try again, ``attempts_left`` more; ``gone`` — expired or revoked,
    #: including by this very attempt.
    reason: Literal["wrong_code", "gone"]
    attempts_left: int


async def verify_endorsement(db: AsyncSession, raw_token: str, code: str) -> CodeRefused | None:
    """Confirm the leader's code — BE-23 (OBT-535). ``None`` is success.

    The request link's rules (``verify_request_link``), for the same reasons: an expired or
    revoked link is ``gone``; a wrong code counts through a guarded ``UPDATE``, so two at once
    are two, and the fifth revokes; the right code marks the first ``verified_at`` and zeroes
    the count, because verifying again from another phone is legitimate. Compared by digest,
    in constant time.

    **It answers no session.** The leader signs once and reads one request, so the proof is the
    row's own ``verified_at``, which the read and the endorsement check: a session would be a
    second credential to revoke for no second use. A spent link still verifies, so the leader
    can reread what was signed.
    """
    link = await find_endorsement(db, raw_token)
    now = datetime.now(UTC)
    if endorsement_status(link, now) in ("expired", "revoked"):
        return CodeRefused(reason="gone", attempts_left=0)

    if not hmac.compare_digest(tokens.digest(code.strip()), link.code_hash):
        counted = await db.execute(
            update(RREndorsementLink)
            .where(RREndorsementLink.id == link.id)
            .values(code_attempts=RREndorsementLink.code_attempts + 1)
            .returning(RREndorsementLink.code_attempts)
        )
        attempts = counted.scalar_one()
        if attempts >= MAX_ENDORSEMENT_ATTEMPTS:
            await db.execute(
                update(RREndorsementLink)
                .where(RREndorsementLink.id == link.id, RREndorsementLink.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            await db.commit()
            return CodeRefused(reason="gone", attempts_left=0)
        await db.commit()
        return CodeRefused(reason="wrong_code", attempts_left=MAX_ENDORSEMENT_ATTEMPTS - attempts)

    link.verified_at = link.verified_at or now
    link.code_attempts = 0
    await db.commit()
    return None
