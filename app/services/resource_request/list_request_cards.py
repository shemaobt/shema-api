from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services.resource_request._cards import CardFacts, cards_of
from app.services.resource_request._editing import editing
from app.services.resource_request.list_requests import list_requests


async def list_request_cards(db: AsyncSession, user: User, app_key: str) -> list[CardFacts]:
    """Every request this caller reaches, as cards — the tracking list's read (FE-46, OBT-514).

    The same rows as ``list_requests``, scoped by the same ``_scope.py``, and the same card
    the PME's project page reads (``list_project_requests``): **one projection, two
    readers**, which is the DoD of BE-24 (OBT-536). ``GET /requests`` stays the envelope the
    form's sync reads; this is the list a screen draws.
    """
    rows = await list_requests(db, user, app_key)
    return await cards_of(db, rows, await editing(db, user, app_key))
