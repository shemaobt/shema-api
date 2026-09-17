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

**The ``network`` consent is checked, and it is not a formality.** It is the consent to being
held and reached at all, so a contact with no such row is one nobody agreed the platform could
use — and reading it would be the act the row exists to authorise. The row is created with the
person and cannot be absent for anything this module wrote; the check is what makes that true
for anything anybody writes later.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError
from app.db.models.auth import User
from app.db.models.shema_consent import ShemaConsentContext
from app.models.shema_intercessor import IntercessorContact
from app.services.shema._directory import revealed_contact, with_consent

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

    if not await with_consent(db, ShemaConsentContext.NETWORK, ids=[intercessor_id]):
        raise AuthorizationError(
            "This contact has no standing consent to be held and reached by the network."
        )

    logger.info(
        "shema intercessor contact revealed",
        extra={
            "shema_operation": "reveal_intercessor_contact",
            "shema_user_id": actor.id,
            "shema_intercessor_id": intercessor_id,
        },
    )
    return IntercessorContact(id=intercessor_id, contact=contact)
