from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRFund
from app.services.resource_request._fund_choices import FundOption, choosable_funds, options_from
from app.services.resource_request.get_request import get_request


async def fund_options(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> list[FundOption]:
    """What the mesa may assign to this request, and what it is assigned now.

    Served per request and not as a global list, because the one row that is not a choice
    — a retired fund this request already draws from — is a fact about *this* request
    (``_fund_choices``). ``get_request`` decides reachability, the same way every other
    read in the module does; the capability is ``assign_fund``, so the route answers only
    the mesa.
    """
    loaded = await get_request(db, request_id, user, app_key)
    assigned: RRFund | None = None
    if loaded.request.fund_id is not None:
        assigned = (
            await db.execute(select(RRFund).where(RRFund.id == loaded.request.fund_id))
        ).scalar_one_or_none()

    return options_from(await choosable_funds(db), assigned)
