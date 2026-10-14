"""A fifteen-minute signed GET for the Pulse's image before the import — gated per call (OBT-585).

The media item's link (``media_download_url``) cannot serve it: the row is a
``ShemaIntakeImage``, not a ``ShemaMediaItem``, and there is no recorded decision to read — the
leader's box in the archived Pulse is the decision until the import makes it one.
``_pending_image`` carries the four gates, their order and the argument for it; this file is the
one that mints, and it stores nothing: the expiry is the whole guarantee.
"""

from __future__ import annotations

import logging
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.auth import User
from app.db.models.shema_form import ShemaIntakeImage, ShemaSubmission
from app.services.oral_collector import gcs_utils
from app.services.shema._media_storage import DOWNLOAD_URL_EXPIRY_MINUTES, GCS_SHEMA_BUCKET
from app.services.shema._pending_image import PendingImageRefusal, pending_image_gates
from app.services.shema._redaction import log_reference
from app.services.shema._scope import Readership, RegionScope
from app.services.shema._submission_archive import archived_answers
from app.services.shema.media_download_url import NOT_SHARED
from app.services.shema.read_submission import scoped_submissions

logger = logging.getLogger(__name__)

OPERATION = "pending_image_download_url"


class PendingImageLink(NamedTuple):
    image: ShemaIntakeImage
    url: str
    expires_in_minutes: int


def _refuse_unknown_submission(
    scope: RegionScope, *, user: User, submission_id: str
) -> NotFoundError:
    """``_scope.refuse_out_of_scope`` for a **submission** id — the same event, named right.

    That function records the id it is given as ``shema_project_id``, and a submission's id
    under that key would break the join by project that ``log_reference`` lines are read with.
    The function is the scope module's and takes a project id only, so the line is written
    here with the submission under its own key and the same facts beside it: who asked, what
    operation, and the scope they hold — never the target's region or any column of it.
    """
    logger.warning(
        "shema scoped submission read found no row: out of region scope or no such id",
        extra={
            "shema_operation": OPERATION,
            "shema_user_id": user.id,
            "shema_submission_id": submission_id,
            "shema_scope_global": scope.global_,
            "shema_scope_regions": sorted(scope.regions),
        },
    )
    return NotFoundError("Project not found")


async def pending_image_download_url(
    db: AsyncSession,
    scope: RegionScope,
    submission_id: str,
    *,
    user: User,
    readership: Readership,
) -> PendingImageLink:
    """The four gates of ``_pending_image``, then one signed URL — or a refusal naming no reason."""
    row = (
        await db.execute(scoped_submissions(scope).where(ShemaSubmission.id == submission_id))
    ).first()
    if row is None:
        raise _refuse_unknown_submission(scope, user=user, submission_id=submission_id)
    submission, _version, project = row

    answers = archived_answers(submission)
    verdict = await pending_image_gates(db, submission, project, answers, readership=readership)
    reference = {
        "shema_operation": OPERATION,
        "shema_user_id": user.id,
        "shema_submission_id": submission.id,
        **log_reference(project),
    }
    if verdict.refusal is PendingImageRefusal.READER:
        logger.warning(
            "shema file refused: the reader is not the coordination of a withheld project",
            extra={**reference, "shema_reader": verdict.reader.value},
        )
        raise AuthorizationError(NOT_SHARED)
    if verdict.refusal is PendingImageRefusal.NO_OBJECT or verdict.image is None:
        raise NotFoundError("File not found")
    if verdict.refusal is PendingImageRefusal.BOX:
        logger.warning(
            "shema file refused: not shared with this audience",
            extra={**reference, "shema_intake_image_id": verdict.image.id},
        )
        raise AuthorizationError(NOT_SHARED)

    url = await gcs_utils.generate_signed_download_url(
        GCS_SHEMA_BUCKET, verdict.image.storage_key, expiry_minutes=DOWNLOAD_URL_EXPIRY_MINUTES
    )
    return PendingImageLink(
        image=verdict.image, url=url, expires_in_minutes=DOWNLOAD_URL_EXPIRY_MINUTES
    )
