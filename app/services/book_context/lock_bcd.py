from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.book_context import BCDStatus, BookContextDocument
from app.utils.stored_time import as_utc

LOCK_TIMEOUT = timedelta(hours=4)


async def lock_bcd(db: AsyncSession, bcd: BookContextDocument, user_id: str) -> BookContextDocument:
    if bcd.status not in (BCDStatus.DRAFT, BCDStatus.REVIEW):
        raise ConflictError("Can only lock a document in draft or review status.")
    if bcd.locked_by and bcd.locked_by != user_id:
        # `locked_at` is nullable and the shared normaliser is not, so the guard stays here,
        # beside the column that can be null. A document nobody has locked has no moment to
        # read, which is not the same as a moment that failed to be read.
        locked_at = as_utc(bcd.locked_at) if bcd.locked_at else None
        if locked_at and (datetime.now(UTC) - locked_at) > LOCK_TIMEOUT:
            pass
        else:
            raise ConflictError("This document is already locked by another user.")
    bcd.locked_by = user_id
    bcd.locked_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(bcd)
    return bcd
