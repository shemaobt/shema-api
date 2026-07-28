from __future__ import annotations

from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.services.annotation_studio import storage
from app.services.annotation_studio.constants import MAX_AUDIO_BYTES

T = TypeVar("T")


async def get_or_404(
    db: AsyncSession, model: type[T], entity_id: str, label: str = "Resource"
) -> T:
    stmt = select(model).where(model.id == entity_id)  # type: ignore[attr-defined]
    result = await db.execute(stmt)
    obj = result.scalar_one_or_none()
    if obj is None:
        raise NotFoundError(f"{label} not found")
    return obj  # type: ignore[return-value]


def enforce_audio_size(key: str) -> None:
    """Reject an over-sized upload at the 'complete' step, deleting the object.

    The presigned PUT URL can't bound the body, so this is the server-side cap.
    Fails open if the size is unknown (see ``storage.object_size``).
    """
    size = storage.object_size(key)
    if size is not None and size > MAX_AUDIO_BYTES:
        storage.delete(key)
        raise ValidationError("Uploaded audio exceeds the maximum allowed size.")
