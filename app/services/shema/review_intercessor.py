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

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shema_intercessor import IntercessorEntry
from app.services.shema._directory import entry_of, mark_reviewed


async def review_intercessor(
    db: AsyncSession,
    intercessor_id: str,
    *,
    now: datetime | None = None,
) -> IntercessorEntry:
    """Stamp the review and answer the entry, which no longer carries the flag.

    A 404 for an unknown id comes from ``_directory``, as every operation on a person does.
    """
    moment = now or datetime.now(UTC)
    await mark_reviewed(db, intercessor_id, now=moment)
    return await entry_of(db, intercessor_id, now=moment)
