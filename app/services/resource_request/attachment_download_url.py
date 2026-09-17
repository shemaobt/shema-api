"""Hand out the budget file the way a private bucket allows: a short-lived signed GET."""

from typing import NamedTuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.auth import User
from app.db.models.resource_request import RRAttachment
from app.services.oral_collector import gcs_utils
from app.services.resource_request._attachment_storage import (
    DOWNLOAD_URL_EXPIRY_MINUTES,
    GCS_RR_BUCKET,
)
from app.services.resource_request.get_request import get_request


class AttachmentLink(NamedTuple):
    attachment: RRAttachment
    url: str
    expires_in_minutes: int


async def attachment_download_url(
    db: AsyncSession, request_id: str, user: User, app_key: str
) -> AttachmentLink:
    """The current attachment plus a signed URL for it, for a caller who reaches the request.

    The guard is ``get_request``'s and nothing more — whoever may read the request may
    read its budget file, and whoever may not learns 404, not 403, for the reason that
    function records. The URL is minted per call and expires in minutes; nothing stores
    it, so there is no lasting link to leak — the row holds only a key into a private
    bucket. Storage serves the bytes; the API never proxies them.
    """
    await get_request(db, request_id, user, app_key)

    attachment = (
        await db.execute(
            select(RRAttachment).where(
                RRAttachment.request_id == request_id, RRAttachment.superseded_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if attachment is None:
        raise NotFoundError(f"Request {request_id} has no attachment")

    url = await gcs_utils.generate_signed_download_url(
        GCS_RR_BUCKET,
        attachment.storage_key,
        expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES,
        response_content_type=attachment.content_type,
    )
    return AttachmentLink(
        attachment=attachment, url=url, expires_in_minutes=DOWNLOAD_URL_EXPIRY_MINUTES
    )
