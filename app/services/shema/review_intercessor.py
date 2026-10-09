"""The one-year review — a Resource Circle member confirming a contact still belongs.

The client answered on 22/sep (4.3) that a contact nobody has used in a year is **reviewed**,
not expired. The list flags it (``reviewDue``, read by ``_directory.review_due``) and this is
the "Revisado" that clears the flag: it stamps ``reviewed_at`` and the year starts again. The
other answer the flag offers is "Remover", which is ``remove_intercessor.py`` unchanged.

**A review is explicit.** Editing a contact, reading it or re-stating a consent does not count,
because none of them is somebody deciding that the person should still be held. The route that
calls this is ``resourceCircle`` only, like every other route of the network.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.auth import User
from app.db.models.shema_change_log import ChangeAction, ChangeSubject
from app.models.shema_intercessor import IntercessorEntry
from app.services.shema import _trail
from app.services.shema._directory import entry_of, mark_reviewed

logger = logging.getLogger(__name__)


async def review_intercessor(
    db: AsyncSession,
    intercessor_id: str,
    *,
    actor: User,
    now: datetime | None = None,
) -> IntercessorEntry:
    """Stamp the review and answer the entry, which no longer carries the flag.

    A 404 for an unknown id comes from ``_directory``, as every operation on a person does.
    The line left behind names who kept the person for another year and which row it was —
    the shape of ``remove_intercessor.py``'s, never the name, the country or the contact.
    """
    moment = now or datetime.now(UTC)
    await _trail.around(
        db,
        lambda: mark_reviewed(db, intercessor_id, now=moment),
        actor=actor,
        subject=ChangeSubject.INTERCESSOR,
        action=ChangeAction.REVIEWED,
        subject_id=intercessor_id,
        fields=("reviewedAt",),
    )
    logger.info(
        "shema intercessor reviewed",
        extra={
            "shema_operation": "review_intercessor",
            "shema_user_id": actor.id,
            "shema_intercessor_id": intercessor_id,
        },
    )
    return await entry_of(db, intercessor_id, now=moment)
