"""Spending a handoff code — the public half of BE-21, and the only way a code pays out.

**The order is the design.** The code is looked up by its digest and its state read; the
account behind it is read from the database, not from the dependency's cache, and an inactive
one is refused as ``/refresh`` refuses it, without spending the code; then the code is spent
and the session issued.

**The spend is a guarded write, not a read and an assignment.** Two exchanges of one code can
both read it as pending; what decides between them is ``UPDATE … WHERE used_at IS NULL`` and
its row count, which is atomic on any engine — the argument ``app/services/device/
claim_device.py`` makes for the Room's claim code, including that ``SELECT … FOR UPDATE`` is a
no-op on SQLite, where the suite would then prove nothing.

**The spend and the payment are one transaction.** ``issue_tokens`` commits, and its commit
carries the spend with the refresh row it writes, so a code is never spent without a session
to show for it, nor a session issued off a code still spendable.

**What is not re-checked is the grant.** The session issued is the one login issues — it is
not scoped to an app — and every route of the destination app checks its own grant on every
request. Refusing here would protect nothing those routes do not already refuse.

**The refusals name the state.** The code is 256 bits, so telling an unknown code from a
spent one is not an oracle, and the receiving app has to say which happened (OBT-538). Every
refusal is logged with its reason and the row's id — never the code — because a spent code
presented again is the one sign that somebody else may have been first.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, InvalidTokenError
from app.db.models.auth import AuthHandoffCode, User
from app.services.auth.get_user_by_id import get_user_by_id
from app.services.auth.issue_tokens import issue_tokens
from app.services.common import tokens

logger = logging.getLogger(__name__)

HandoffRefusal = Literal["unknown", "expired", "used"]


class HandoffRefused(InvalidTokenError):
    """A code that opens nothing, and which of the three reasons it was.

    An ``InvalidTokenError`` so that a caller which does not map it still answers 401 through
    the global handler; ``app/api/auth.py`` maps ``reason`` to a ``code`` of its own.
    """

    def __init__(self, reason: HandoffRefusal) -> None:
        super().__init__(f"Handoff code refused: {reason}")
        self.reason: HandoffRefusal = reason


@dataclass(frozen=True)
class ExchangedHandoff:
    user: User
    access_token: str
    refresh_token: str
    context: dict[str, Any] | None


@dataclass
class _CodeState:
    """What ``tokens.status`` reads off a code, with the revocation a code cannot have.

    ``TokenRow`` asks for ``revoked_at`` and ``auth_handoff_codes`` has no such column: a code
    lives a minute and nothing takes one back. A plain dataclass because the protocol's
    attributes are settable and a frozen one does not satisfy it.
    """

    expires_at: datetime
    used_at: datetime | None
    revoked_at: datetime | None = None


def _refuse(reason: HandoffRefusal, code: AuthHandoffCode | None) -> HandoffRefused:
    logger.warning(
        "handoff code refused",
        extra={"reason": reason, "handoff_id": None if code is None else code.id},
    )
    return HandoffRefused(reason)


async def exchange_handoff(
    db: AsyncSession, raw_code: str, *, now: datetime | None = None
) -> ExchangedHandoff:
    """Spend ``raw_code`` for a session of the person who asked for it.

    Raises ``HandoffRefused`` for a code that is unknown, past its minute or already spent —
    in the order ``tokens.status`` reads them, so a spent code presented after its minute
    reads as expired — and ``AuthorizationError`` for an account no longer active.
    """
    now = now or datetime.now(UTC)
    stmt = select(AuthHandoffCode).where(AuthHandoffCode.code_hash == tokens.digest(raw_code))
    code = (await db.execute(stmt)).scalar_one_or_none()
    if code is None:
        raise _refuse("unknown", None)

    state = tokens.status(_CodeState(expires_at=code.expires_at, used_at=code.used_at), now)
    if state != "pending":
        raise _refuse("expired" if state == "expired" else "used", code)

    user = await get_user_by_id(db, code.user_id)
    if user is None or not user.is_active:
        raise AuthorizationError("Inactive or missing user")

    spent = await db.execute(
        update(AuthHandoffCode)
        .where(AuthHandoffCode.id == code.id, AuthHandoffCode.used_at.is_(None))
        .values(used_at=now)
    )
    if spent.rowcount != 1:
        raise _refuse("used", code)

    context = code.context
    access_token, refresh_token = await issue_tokens(db, user)
    return ExchangedHandoff(
        user=user, access_token=access_token, refresh_token=refresh_token, context=context
    )
