"""The reads a request link's holder shares with an account — BE-26 (OBT-537), PR B.

Four reads answer both subjects: the listing, one request, the cards and the team's status.
Each takes a **reader** — a ``User`` or a ``LinkActor`` — and sends it down the path that
already exists for it: an account keeps ``_scope.py``'s reach, byte for byte what it was, and
a link reaches its own requests (``_link_actor.py``). One dispatch here rather than a branch in
every router, so the house rule that routers only parse and call holds.

A link reads what GATE-03 D4 gives a team — the request, its status, its card — and nothing of
the evaluation: none of these four reads touches it beyond the ``decision`` and ``team_note``
the status projection already serves the team.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.resource_request import RRRequest
from app.services.resource_request._cards import CardFacts, cards_of
from app.services.resource_request._editing import Edits, editing
from app.services.resource_request._link_actor import LinkActor, get_link_request, link_requests
from app.services.resource_request._loading import Loaded
from app.services.resource_request.get_request import get_request
from app.services.resource_request.list_request_cards import list_request_cards
from app.services.resource_request.list_requests import list_requests
from app.services.resource_request.request_status import RequestStatus, status_of

Reader = User | LinkActor


async def edits_for(db: AsyncSession, reader: Reader, app_key: str) -> Edits:
    if isinstance(reader, LinkActor):
        return reader
    return await editing(db, reader, app_key)


async def requests_for(db: AsyncSession, reader: Reader, app_key: str) -> list[RRRequest]:
    if isinstance(reader, LinkActor):
        return await link_requests(db, reader)
    return await list_requests(db, reader, app_key)


async def request_for(db: AsyncSession, request_id: str, reader: Reader, app_key: str) -> Loaded:
    if isinstance(reader, LinkActor):
        return await get_link_request(db, request_id, reader)
    return await get_request(db, request_id, reader, app_key)


async def cards_for(db: AsyncSession, reader: Reader, app_key: str) -> list[CardFacts]:
    """An account's cards are ``list_request_cards``' — the BE-24 owner of *one projection, two
    readers* — and a link's are the same ``cards_of`` over its own rows."""
    if isinstance(reader, LinkActor):
        return await cards_of(db, await link_requests(db, reader), reader)
    return await list_request_cards(db, reader, app_key)


async def status_for(
    db: AsyncSession, request_id: str, reader: Reader, app_key: str
) -> RequestStatus:
    """The team's status, projected by ``request_status.status_of`` for either reader."""
    return await status_of(db, (await request_for(db, request_id, reader, app_key)).request)
