"""Editing a network contact. ``addedAt`` is not reachable and consent is not touched.

``addedAt`` is when the platform began holding this person's data, which is the fact a
retention question is asked against — FE-44 §8.5 records that wave 1 stores it *so the question
is answerable*, and §9.6 states the rule as *``addedAt`` survives an edit*. The way it survives
here is that the payload has no field for it.

**Changing the contact does not re-ask for consent, and that is deliberate.** The consent is to
being held and reached by the network, not to a particular telephone; somebody who changes
their number has withdrawn nothing. What would need a new basis is a new person, and that is a
create.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_intercessor import IntercessorEntry, IntercessorUpdate
from app.services.shema._directory import edit_person, entry_of


async def update_intercessor(
    db: AsyncSession,
    intercessor_id: str,
    *,
    payload: IntercessorUpdate,
) -> IntercessorEntry:
    """Apply the fields the payload carries; absent means unchanged.

    ``exclude_unset`` and not ``exclude_none``: *not sent* and *sent as null* are different
    answers, and ``sensitiveCountry`` is where the difference bites — a partial edit of a name
    must not silently unflag somebody.
    """
    await edit_person(db, intercessor_id, payload.model_dump(exclude_unset=True))
    return await entry_of(db, intercessor_id)
