"""Take one image through one link — the bytes to the private bucket, a pointer to the table.

The upload happens **before** the answers: the leader attaches the photo, the console posts it
here and gets an id back, and the id is what the ``image`` answer of the Pulse carries
(``app/utils/shema_forms.py``). ``receive_submission`` then binds the two — an id another link
uploaded, or one already bound to a Pulse, is refused there.

**It writes nothing of the record and nothing a reader can reach.** A ``shema_intake_images``
row is on no surface: the ficha's media and the card's ``hasMedia`` read ``shema_media_items``,
which the import mints later (``import_submission.py``). What a forwarded link can do with this
route is fill a bucket, and the ceiling and the rate limits are the answer to that.

The key is ``_media_storage.storage_key`` scoped to **this row's** id — content-addressed, the
leader's filename never in it, the project's slug (which names the place) never in it. The media
item the import mints keeps that same key, so the two rows name one object and no copy is made.
"""

from __future__ import annotations

import hashlib
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.shema_form import ShemaIntakeImage
from app.services.oral_collector import gcs_utils
from app.services.shema._intake_image_rules import IMAGE_EXTENSIONS, image_type
from app.services.shema._intake_tokens import verify_intake_token
from app.services.shema._media_storage import GCS_SHEMA_BUCKET, MEDIA, storage_key

logger = logging.getLogger(__name__)


async def store_intake_image(
    db: AsyncSession,
    raw_token: str,
    *,
    data: bytes,
    content_type: str | None,
    file_name: str | None,
) -> ShemaIntakeImage:
    """Verify the link, prove the bytes, put them in the bucket, keep the pointer."""
    link = await verify_intake_token(db, raw_token)
    canonical = image_type(content_type, data)
    image = ShemaIntakeImage(
        id=str(uuid.uuid4()),
        project_id=link.project_id,
        intake_link_id=link.id,
        storage_key="",
        file_name=(file_name or "")[:300] or None,
        content_type=canonical,
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
    )
    # The id is minted here and not by the column default: the key is scoped to it, and a
    # default would only exist after the flush — after the key was already written with ``None``.
    image.storage_key = storage_key(MEDIA, image.id, image.sha256, IMAGE_EXTENSIONS[canonical])
    await gcs_utils.upload_gcs_object(GCS_SHEMA_BUCKET, image.storage_key, data, canonical)
    db.add(image)
    await db.commit()
    logger.info(
        "shema intake image stored",
        extra={
            "shema_operation": "store_intake_image",
            "shema_intake_link_id": link.id,
            "shema_intake_image_id": image.id,
            "shema_image_bytes": image.size_bytes,
        },
    )
    return image
