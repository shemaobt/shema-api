"""Putting in the directory somebody already in the network — found by their contact (OBT-681).

The ``directory`` consent was offered only at the create. A person who joined the network without
it and later agrees to be listed is on no screen — the directory shows only who consented to it,
and the rest is a number (``list_intercessors.py``) — so the console never holds their id and
``PUT …/{id}/consents/directory`` was reachable by the API alone. The coordination is the one
talking to the person, so it has what the screen does not: the contact they were asked through.

**The search is the write.** The member is found and the consent recorded in one call, and the
answer is the entry, already listable. Nothing about the person — not a name, not whether they are
held at all — reaches the console before the consent that lets them appear is stored, signed and
in the change log. The alternative, finding first and recording with the existing ``PUT``, shows a
hidden person to whoever typed a contact; showing the hidden to the coordination outright lists
people who withheld exactly that, and what to do with them is the client's (``docs/shema.md`` §10
item 8).

**Asked twice is answered, not refused and not restamped.** Somebody already listed is answered
with their entry and ``recorded=False``: their basis and date are the evidence of the answer they
gave, and a lookup by contact is not where a stated consent is overwritten —
``_directory.record_where_missing``'s rule, for the same reason. ``set_intercessor_consent`` is the
door that restamps, by id.

**A search that finds nobody leaves a log line**, with who asked and never what: a hit is a signed
write, so the line is what keeps a miss from being a silent way to ask whether a contact is held.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.db.models.auth import User
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import DirectoryConsentByContact, IntercessorEntry
from app.services.shema._directory import entry_of, member_reached_at, with_consent
from app.services.shema.set_intercessor_consent import set_intercessor_consent

logger = logging.getLogger(__name__)


class DirectoryAdmission(NamedTuple):
    """The member as the directory now lists them, and whether this call recorded the consent."""

    entry: IntercessorEntry
    recorded: bool


async def admit_to_directory(
    db: AsyncSession,
    *,
    payload: DirectoryConsentByContact,
    actor: User,
) -> DirectoryAdmission:
    """Record ``directory`` for the one member reached at ``payload.contact``, on its basis.

    The consent row carries ``recorded_by`` and ``recorded_at`` and the trail the actor's name and
    the hour, both through ``set_intercessor_consent`` — the same two marks the ``PUT`` by id and
    the create leave, so the three doors cannot disagree about who listed somebody.
    """
    try:
        person_id = await member_reached_at(db, payload.contact)
    except (NotFoundError, ConflictError) as refusal:
        logger.info(
            "shema directory consent by contact found no single member",
            extra={
                "shema_operation": "admit_to_directory",
                "shema_user_id": actor.id,
                "shema_refusal": type(refusal).__name__,
            },
        )
        raise
    if await with_consent(db, ShemaConsentContext.DIRECTORY, ids=[person_id]):
        return DirectoryAdmission(entry=await entry_of(db, person_id), recorded=False)
    entry = await set_intercessor_consent(
        db, person_id, ShemaConsentContext.DIRECTORY, basis=payload.basis, actor=actor
    )
    return DirectoryAdmission(entry=entry, recorded=True)
