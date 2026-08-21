from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.db.models.book_context import BCDStatus, BookContextDocument
from app.utils.stored_time import as_utc

LOCK_TIMEOUT = timedelta(hours=4)


async def lock_bcd(db: AsyncSession, bcd: BookContextDocument, user_id: str) -> BookContextDocument:
    """Take the single-editor lease on a document, or refuse because somebody holds it.

    A lease older than ``LOCK_TIMEOUT`` is taken over. One with no moment recorded is not:
    ``locked_at`` is nullable and an unknown age is not an expired one, so the guard lives
    here rather than in ``as_utc`` — which is non-optional, and would spread this column's
    nullability to four callers that cannot receive a null.
    """
    if bcd.status not in (BCDStatus.DRAFT, BCDStatus.REVIEW):
        raise ConflictError("Can only lock a document in draft or review status.")
    if bcd.locked_by and bcd.locked_by != user_id:
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
