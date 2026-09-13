"""Removal, which **erases**: the row is gone and the contact is absent from storage.

``docs/shema.md`` §5.7 and FE-44 §8.5 both spell it the same way — *no tombstone, no
``removed`` flag, the contact absent from storage* — and ``app/db/models/shema_intercessor.py``
has no soft-delete column so that the wrong thing cannot be written. The consent rows go with
the person by ``ON DELETE CASCADE``: a consent record outliving its subject would be retained
personal data about somebody the system no longer holds, which is the same defect the
no-tombstone rule refuses, arriving one table over.

**What is left behind is a log line with no person in it.** The actor, the id and the
operation are recorded so an operator can answer *did this removal happen and who did it* —
the question anybody investigating a deletion actually asks. The name, the country and the
contact are **not** in the line, and that is the point of it existing in this shape:
``refuse_out_of_scope`` in ``_scope.py`` makes the same trade for the same reason, that a log
is read by more people and kept longer than a response body. A removal audit **row** would be
the tombstone by another name.

**Nothing else in this module holds a reference to a network contact**, so removal takes effect
everywhere in one statement rather than in a sweep. That is not luck: §5.7 forbids a foreign
key from this table to anything, in either direction, which is what makes *removal removes from
every output* a property of the schema instead of a checklist. ``_directory.leaving_directory``
reads the table on every call and caches nothing, so a person removed is absent from the next
export with no cleanup step — the derived-wall property of FE-44 §8.2, held here by the same
means.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.services.shema._directory import erase_person

logger = logging.getLogger(__name__)


async def remove_intercessor(db: AsyncSession, intercessor_id: str, *, actor: User) -> None:
    """Erase one contact and everything recorded about them."""
    await erase_person(db, intercessor_id)

    logger.info(
        "shema intercessor erased",
        extra={
            "shema_operation": "remove_intercessor",
            "shema_user_id": actor.id,
            "shema_intercessor_id": intercessor_id,
        },
    )
