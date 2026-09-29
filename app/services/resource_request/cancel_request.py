from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError
from app.services.resource_request._loading import Loaded
from app.services.resource_request._writer import Writer, reach_for_writing


async def cancel_request(db: AsyncSession, request_id: str, user: Writer, app_key: str) -> Loaded:
    """Give an open instance up, so another member of the project may start one.

    GATE-04 D6 (OBT-519, Daniel, 23/sep/2026), BE-25 (OBT-534). Only the starter or the Admin
    cancels — or the request link that started it (BE-26) — through ``reach_for_writing``,
    which also answers 409 to one already cancelled; and only a
    draft: a submitted request is the mesa's to decide, and the way back from a decision is a
    revision.

    **Cancelling marks and never deletes.** ``cancelled_at`` is written and the row stays, with
    its sections, its budget and its BE-15 field trail, which is written about this row and
    would be orphaned by a delete. The partial unique index stops counting it, and that alone
    is what frees the project. The listing stops showing it (``list_requests``) and reading it
    by id still works — it is history, not a draft anyone may type into.

    GATE-04's own table says *"cancelar apaga o rascunho"*; this issue's spec narrowed it to a
    mark, and the narrowing is Daniel's: deleting a draft is the BE-19 migration's, for the
    test requests only.
    """
    loaded = await reach_for_writing(db, request_id, user, app_key)

    if loaded.request.submitted_at is not None:
        raise ConflictError(
            "This request was already submitted; the mesa decides it now, and cancelling "
            "does not reach it."
        )

    loaded.request.cancelled_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(loaded.request)
    return loaded
