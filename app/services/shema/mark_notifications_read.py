"""Marking the panel's ids seen — the one write ``POST /notifications/read`` makes.

**Two kinds of id, one call.** A delivered notice's id is the platform's own primary key, so
marking it read is ``app/services/notifications/mark_as_read.py``, unchanged. A stale id has no
row to flip a column on — ``app/models/shema_notification.py``'s module docstring is why — so
its read state is a fact recorded in ``shema_notification_reads`` instead, keyed on the id
itself. A caller sends a mixed batch without knowing which kind an id is, because FE-44 §5.8's
whole point is that an id is enough to act on without a second lookup first.

**An id that names nobody's notice is a no-op, not a failure.** A stale entry's id changes with
its own date; a screen a client left open across a save is showing an id that has already aged
out from underneath it. Refusing the whole batch for one stale id a client could not have known
was gone would make the common case — most of a batch is fresh — pay for the rare one.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.shema_notification import ShemaNotificationRead
from app.services.notifications import mark_as_read


async def _mark_derived_read(db: AsyncSession, user_id: str, entry_ids: list[str]) -> None:
    """Insert every missing ``(user, entry)`` pair in ``entry_ids`` with a single commit.

    One ``select`` finds which of the batch already has a row, then every missing pair is
    ``add``ed in-memory — no per-id round trip — before the one commit at the end. This module's
    tables run on SQLite in the suite and on PostgreSQL in production (``docs/shema.md`` §7.2),
    so a dialect-specific ``ON CONFLICT`` upsert would work on one and not the other; the primary
    key already refuses a second row, and the batched read that checks for one first is the
    portable half of the same guarantee.
    """
    stmt = select(ShemaNotificationRead.entry_id).where(
        ShemaNotificationRead.user_id == user_id,
        ShemaNotificationRead.entry_id.in_(entry_ids),
    )
    existing = set((await db.execute(stmt)).scalars())
    now = datetime.now(UTC)
    for entry_id in entry_ids:
        if entry_id in existing:
            continue
        db.add(ShemaNotificationRead(user_id=user_id, entry_id=entry_id, read_at=now))
    await db.commit()


async def mark_notifications_read(db: AsyncSession, user_id: str, ids: list[str]) -> None:
    """Mark every id in ``ids`` read, whichever of the two stores it belongs to.

    The derived half is one read plus one commit for the whole batch (see
    ``_mark_derived_read``). The delivered half still goes through ``mark_as_read`` per id,
    unchanged — it already owns the row's ``is_read`` write and its own commit, and is not this
    module's to refactor.
    """
    stale_ids = [entry_id for entry_id in ids if entry_id.startswith("stale:")]
    if stale_ids:
        await _mark_derived_read(db, user_id, stale_ids)

    for entry_id in ids:
        if entry_id.startswith("stale:"):
            continue
        try:
            await mark_as_read(db, entry_id, user_id)
        except NotFoundError:
            continue
