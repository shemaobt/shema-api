"""One contact, for one person, one call — and the line that says it was read.

The collection carries no contact string (``list_intercessors.py``), because the issue's own
sentence is that *an endpoint that returns every phone number in one call is a data-loss
incident waiting for one compromised session*. This is the other half of that decision: the
way to actually reach somebody, which has to exist, sized so that reading the directory costs
one request per person.

**The audit line is here and not in ``_directory.reveal_contact``**, because this is where the
caller is in hand. The line names who read it and whose contact it was, and carries **neither
the contact nor the name** — the same trade ``_scope.refuse_out_of_scope`` makes and for the
same reason: a log is read by more people and kept longer than a response body, so it holds
the fact of the read and not its content.

**Only somebody listed in the directory is revealed** (OBT-574, Karina's 4b): the gate is
``_directory.revealed_contact``'s, beside the read it guards, as the list's is
``listable_ids``'s.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.models.shema_intercessor import IntercessorContact
from app.services.shema._directory import revealed_contact

logger = logging.getLogger(__name__)


async def reveal_intercessor_contact(
    db: AsyncSession,
    intercessor_id: str,
    *,
    actor: User,
) -> IntercessorContact:
    """The real contact string, recorded as read.

    The 404 for an unknown id comes from ``_directory``, which is also where the consent
    check's subject is read, so the two refusals cannot disagree about whether the row exists.
    """
    contact = await revealed_contact(db, intercessor_id)

    logger.info(
        "shema intercessor contact revealed",
        extra={
            "shema_operation": "reveal_intercessor_contact",
            "shema_user_id": actor.id,
            "shema_intercessor_id": intercessor_id,
        },
    )
    return IntercessorContact(id=intercessor_id, contact=contact)
