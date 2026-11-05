"""Who a user id names today, for the readers that show a person and never store one.

``display_names_of`` is the one statement behind every *who* this module answers by name —
the card's *em preenchimento por X* (``_cards``) and the trail's ``changed_by_name``
(``list_request_history``, OBT-685). It answers ``display_name`` and nothing else: the
e-mail of whoever on the mesa or the Gestor edited a team's request is not the team's to
read, and a user with no ``display_name`` answers ``None`` rather than a stand-in, so the
screen says it has no name instead of inventing one. A name is resolved at read time
precisely because it is not append-only — the trail is (§4.4).
"""

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User


async def display_names_of(db: AsyncSession, ids: Iterable[str]) -> dict[str, str | None]:
    """``{user_id: display_name}`` for every id in ``ids`` — one statement whatever their count."""
    wanted = set(ids)
    if not wanted:
        return {}
    rows = await db.execute(select(User.id, User.display_name).where(User.id.in_(wanted)))
    return dict(rows.tuples().all())
