"""Attach the budget file to a request — upload, then supersede, never delete."""

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.auth import User
from app.db.models.resource_request import RRAttachment
from app.services.oral_collector import gcs_utils
from app.services.resource_request._attachment_rules import (
    ATTACHMENT_EXTENSIONS,
    MAX_ATTACHMENT_BYTES,
    attachment_type,
)
from app.services.resource_request._attachment_storage import GCS_RR_BUCKET, storage_key
from app.services.resource_request.get_request import get_request


def _display_name(filename: str | None, extension: str) -> str:
    """The name the file is shown under — display data only, never part of a key.

    Path separators are stripped because a client's filename is client-typed text; what
    survives is the last segment, defaulting to the frozen name the storage key uses.
    """
    candidate = (filename or "").replace("\\", "/").rsplit("/", 1)[-1].strip()
    return candidate[:255] if candidate else f"orcamento{extension}"


async def store_attachment(
    db: AsyncSession,
    request_id: str,
    user: User,
    app_key: str,
    *,
    data: bytes,
    content_type: str | None,
    filename: str | None = None,
) -> RRAttachment:
    """Store the budget file for a draft this caller reaches, replacing any current one.

    The scope guard is ``get_request``'s — the same 404-for-out-of-scope the request
    itself answers — and the draft rule is ``update_draft``'s: a submitted request is
    frozen under the mesa's eyes, so the file may not move either; the way back in is a
    revision.

    **A replacement supersedes the current row and deletes nothing**, neither the row nor
    its object. The row survives because the mesa may have read that file and the record
    of what was here is part of the trail; the object survives because keys are
    content-addressed and a superseded row may share its key with the current one
    (identical bytes re-uploaded), so a sweep could destroy the very file it thinks it is
    tidying after. An orphaned object is storage; a broken history is evidence gone.

    The bytes land in the bucket **before** any row moves (the sound-necklace order): a
    failed upload raises here, no pointer has moved, and the request keeps the attachment
    it had. A failure after upload leaves an orphan object nothing references — the same
    harmless residue ``store_artifacts`` accepts, for the same reason.

    The size ceiling is the router's to answer with 413 before reading the body; the
    check here is the backstop for a caller that is not the router, and it refuses as a
    validation error because by this point the bytes have already been read.
    """
    loaded = await get_request(db, request_id, user, app_key)

    if loaded.request.submitted_at is not None:
        raise ConflictError(
            "This request was already submitted. Replacing its file now would change what "
            "the mesa is evaluating; open a revision instead."
        )

    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValidationError(
            f"The attachment exceeds the {MAX_ATTACHMENT_BYTES // (1024 * 1024)} MB limit."
        )

    canonical = attachment_type(content_type, data)
    extension = ATTACHMENT_EXTENSIONS[canonical]
    sha256 = hashlib.sha256(data).hexdigest()
    key = storage_key(request_id, sha256, extension)

    await gcs_utils.upload_gcs_object(GCS_RR_BUCKET, key, data, canonical)

    current = (
        await db.execute(
            select(RRAttachment).where(
                RRAttachment.request_id == request_id, RRAttachment.superseded_at.is_(None)
            )
        )
    ).scalar_one_or_none()
    if current is not None:
        current.superseded_at = datetime.now(UTC)

    attachment = RRAttachment(
        request_id=request_id,
        filename=_display_name(filename, extension),
        content_type=canonical,
        size_bytes=len(data),
        sha256=sha256,
        storage_key=key,
        uploaded_by=user.id,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)
    return attachment
