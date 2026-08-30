import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.resource_request import RRFund


async def create_fund(db: AsyncSession, *, name: str) -> RRFund:
    """Mint a fund: the server's own id, the Gestor's name, no money.

    **The id is opaque and the server cunha it** — ``uuid4().hex``, 32 characters, exactly
    the width ``rr_funds.id`` has carried since ``20260825_rr01``. Not a slug of the name,
    which is the shape a reader reaches for first and the one that breaks on the next
    line of this module's DoD: renaming must not touch the id, and a slug would keep the
    old name legible inside every ledger entry that cites the fund, forever. Not the
    client's to send either — an id that arrives on the wire is a name space the client
    owns, and the only thing a caller may say about a fund is what it is called.

    **``linguas`` is the one exception, and it is inherited rather than granted here.**
    That row is written by ``20260830_rr04`` with the id it already had, because the
    vendored emission carries it, the seed's ten cards write ``fund_id = "linguas"``, and
    minting a uuid for it would make three places disagree. No route can produce a second
    readable id.

    The name is the fund's only human identity — the id is never shown — so it is
    required, trimmed, and unique. The duplicate is refused **here as a 409** rather than
    left to ``uq_rr_funds_name``: the constraint would surface as an
    ``IntegrityError`` naming a constraint, and the person reading it typed a name. The
    constraint stays as the guarantee under the check, for the caller that does not come
    through this function and for the race where two Gestores type the same name at once.

    A retired fund keeps its name against this check, which is deliberate: its name still
    appears in the ledger's history, and a second fund wearing it would make one history
    read as two.

    Born with no movements, so all three of its figures are zero — the state GATE-01 D6
    has every fund born in, and the reason ``fund_balances`` answers zeros for a fund
    absent from the ledger rather than skipping it.
    """
    cleaned = name.strip()
    if not cleaned:
        raise ValidationError("A fund needs a name: it is the only identity of it anyone sees.")

    taken = (await db.execute(select(RRFund.id).where(RRFund.name == cleaned))).scalar_one_or_none()
    if taken is not None:
        raise ConflictError(f"A fund is already called {cleaned!r}.")

    fund = RRFund(id=uuid.uuid4().hex, name=cleaned)
    db.add(fund)
    await db.commit()
    await db.refresh(fund)
    return fund
