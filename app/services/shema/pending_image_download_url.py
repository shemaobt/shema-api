"""A fifteen-minute signed GET for the Pulse's image before the import — gated per call (OBT-585).

The media item's link (``media_download_url``) cannot serve it: the row is a
``ShemaIntakeImage``, not a ``ShemaMediaItem``, and there is no recorded decision to read — the
leader's box in the archived Pulse is the decision until the import makes it one.
``_pending_image`` carries the four gates and the argument; this file is the one that mints, and
it stores nothing: the expiry is the whole guarantee.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.auth import User
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.services.oral_collector import gcs_utils
from app.services.shema._media_sharing import pulse_image_authorized, reader_may_read_media
from app.services.shema._media_storage import DOWNLOAD_URL_EXPIRY_MINUTES, GCS_SHEMA_BUCKET
from app.services.shema._pending_image import pending_image_of
from app.services.shema._redaction import log_reference
from app.services.shema._scope import Readership, RegionScope, refuse_out_of_scope
from app.services.shema._submission_archive import archived_answers
from app.services.shema.media_download_url import NOT_SHARED
from app.services.shema.read_submission import scoped_submissions

logger = logging.getLogger(__name__)


class PendingImageLink(NamedTuple):
    image: ShemaIntakeImage
    url: str
    expires_in_minutes: int


async def pending_image_download_url(
    db: AsyncSession,
    scope: RegionScope,
    submission_id: str,
    *,
    user: User,
    readership: Readership,
) -> PendingImageLink:
    """The four gates of ``_pending_image``, then one signed URL — or a refusal naming no reason."""
    operation = "pending_image_download_url"
    row = (
        await db.execute(scoped_submissions(scope).where(ShemaSubmission.id == submission_id))
    ).first()
    if row is None:
        raise refuse_out_of_scope(scope, user=user, operation=operation, project_id=submission_id)
    submission, _version, project = row

    answers = archived_answers(submission)
    image = await pending_image_of(db, submission, answers)
    if image is None:
        raise NotFoundError("File not found")

    reference = {
        "shema_operation": operation,
        "shema_user_id": user.id,
        "shema_submission_id": submission.id,
        "shema_intake_image_id": image.id,
        **log_reference(project),
    }
    if not pulse_image_authorized(answers):
        logger.warning("shema file refused: not shared with this audience", extra=reference)
        raise AuthorizationError(NOT_SHARED)
    reader = readership.reader_of(project.region_key)
    if not reader_may_read_media(project, reader):
        logger.warning(
            "shema file refused: the reader is not the coordination of a withheld project",
            extra={**reference, "shema_reader": reader.value},
        )
        raise AuthorizationError(NOT_SHARED)

    url = await gcs_utils.generate_signed_download_url(
        GCS_SHEMA_BUCKET, image.storage_key, expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES
    )
    return PendingImageLink(image=image, url=url, expires_in_minutes=DOWNLOAD_URL_EXPIRY_MINUTES)
