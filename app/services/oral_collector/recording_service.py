import logging
import re
from datetime import UTC, datetime, timedelta

import google.auth
import google.auth.transport.requests
import inngest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import (
    ACTIVE_UPLOAD_STATUSES,
    USER_SETTABLE_CLEANING_STATUSES,
    OCRecordingEvent,
    SplittingStatus,
    UploadStatus,
)
from app.core.exceptions import (
    AuthorizationError,
    ConflictError,
    InvalidCleaningStatusError,
    NotFoundError,
    SecondaryClassificationConflictError,
    UnknownReferenceError,
    ValidationError,
)
from app.core.inngest_client import inngest_client
from app.db.models.auth import User
from app.db.models.oc_recording import OC_Recording
from app.db.models.oc_storyteller import OC_Storyteller
from app.db.models.project import ProjectUserAccess
from app.inngest.schemas import UploadConfirmedPayload
from app.models.oc_recording import (
    RecordingCreate,
    RecordingUpdate,
    ResumableUploadUrlResponse,
    UploadUrlResponse,
)
from app.services.oral_collector.constants import GCS_OC_BUCKET, GCS_OC_PROJECT
from app.services.oral_collector.gcs_utils import GCS_PUBLIC_BASE, content_type_for_format

logger = logging.getLogger(__name__)

_gcs_client = None
_signing_credentials = None

RESUMABLE_CHUNK_SIZE = 8 * 1024 * 1024


def secondary_equals_primary(
    *,
    primary_register_id: str | None,
    primary_genre_id: str | None,
    primary_subcategory_id: str | None,
    secondary_register_id: str | None,
    secondary_genre_id: str | None,
    secondary_subcategory_id: str | None,
) -> bool:
    has_any_secondary = (
        secondary_register_id is not None
        or secondary_genre_id is not None
        or secondary_subcategory_id is not None
    )
    if not has_any_secondary:
        return False
    return (
        primary_register_id == secondary_register_id
        and primary_genre_id == secondary_genre_id
        and primary_subcategory_id == secondary_subcategory_id
    )


def _get_gcs_client():  # type: ignore[no-untyped-def]
    from google.cloud import storage

    global _gcs_client
    if _gcs_client is None:
        _gcs_client = storage.Client(project=GCS_OC_PROJECT)
    return _gcs_client


def _get_signing_info() -> tuple[str, str]:
    global _signing_credentials
    if _signing_credentials is None:
        _signing_credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
    if not _signing_credentials.valid:
        _signing_credentials.refresh(google.auth.transport.requests.Request())
    creds = _signing_credentials
    return creds.service_account_email, creds.token  # type: ignore[attr-defined]


FORMAT_EXTENSIONS: dict[str, str] = {
    "m4a": ".m4a",
    "aac": ".aac",
    "mp3": ".mp3",
    "wav": ".wav",
    "ogg": ".ogg",
    "webm": ".webm",
}

SIGNED_URL_EXPIRY_MINUTES = 15


async def list_recordings(
    db: AsyncSession,
    project_id: str,
    *,
    genre_id: str | None = None,
    subcategory_id: str | None = None,
    upload_status: str | None = None,
    cleaning_status: str | None = None,
    user_id: str | None = None,
    storyteller_id: str | None = None,
    title: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[OC_Recording]:

    stmt = (
        select(OC_Recording)
        .where(OC_Recording.project_id == project_id)
        .where(OC_Recording.splitting_status != SplittingStatus.ARCHIVED_AFTER_SPLIT)
        .order_by(OC_Recording.recorded_at.desc())
    )
    if genre_id:
        stmt = stmt.where(OC_Recording.genre_id == genre_id)
    if subcategory_id:
        stmt = stmt.where(OC_Recording.subcategory_id == subcategory_id)
    if upload_status:
        stmt = stmt.where(OC_Recording.upload_status == upload_status)
    else:
        stmt = stmt.where(OC_Recording.upload_status.in_(ACTIVE_UPLOAD_STATUSES))
    if cleaning_status:
        stmt = stmt.where(OC_Recording.cleaning_status == cleaning_status)
    if user_id:
        stmt = stmt.where(OC_Recording.user_id == user_id)
    if storyteller_id:
        stmt = stmt.where(OC_Recording.storyteller_id == storyteller_id)
    if title:
        stmt = stmt.where(OC_Recording.title == title.strip())
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def get_recording(db: AsyncSession, recording_id: str) -> OC_Recording:

    stmt = select(OC_Recording).where(OC_Recording.id == recording_id)
    result = await db.execute(stmt)
    recording = result.scalar_one_or_none()
    if not recording:
        raise NotFoundError("Recording not found")
    return recording


async def check_recording_access(db: AsyncSession, recording: OC_Recording, user_id: str) -> None:

    acting_user = await db.get(User, user_id)
    if acting_user is not None and acting_user.is_platform_admin:
        return
    if recording.user_id == user_id:
        return
    stmt = select(ProjectUserAccess).where(
        ProjectUserAccess.project_id == recording.project_id,
        ProjectUserAccess.user_id == user_id,
        ProjectUserAccess.role == "manager",
    )
    result = await db.execute(stmt)
    if result.scalar_one_or_none() is None:
        raise AuthorizationError(
            "Only the recording owner, a project manager, or a platform admin "
            "can modify this recording"
        )


def _normalize_title(value: str | None) -> str | None:
    return (value or "").strip() or None


TITLE_UNIQUE_INDEX = "uq_oc_recordings_project_title"


def _is_exempt_from_title_uniqueness(recording: OC_Recording) -> bool:
    """Mirror of the partial index predicate: split segments and archived split parents
    sit outside it, so they may carry a title another recording already holds."""
    return (
        recording.split_from_id is not None
        or recording.splitting_status == SplittingStatus.ARCHIVED_AFTER_SPLIT
    )


UNKNOWN_REFERENCE_MESSAGE = (
    "This recording points at a record that does not exist — check project_id, genre_id, "
    "subcategory_id, secondary_genre_id, secondary_subcategory_id and storyteller_id"
)

CALLER_REFERENCE_FIELDS = (
    "project_id",
    "genre_id",
    "subcategory_id",
    "secondary_genre_id",
    "secondary_subcategory_id",
    "storyteller_id",
)

_FOREIGN_KEY_CONSTRAINT = re.compile(r'foreign key constraint "([^"]+)"', re.IGNORECASE)


def _violated_reference_field(exc: IntegrityError) -> str | None:
    """The column behind a foreign key violation, or None when the error names none.

    Postgres puts the constraint in the message and constraints are named after their
    column, so the field falls out of it. SQLite says only that some foreign key failed.
    The longest match wins: ``oc_recordings_secondary_genre_id_fkey`` contains
    ``genre_id`` too, and reporting the primary would send the caller to a field that is
    fine.
    """
    match = _FOREIGN_KEY_CONSTRAINT.search(str(exc.orig))
    if match is None:
        return None
    constraint = match.group(1)
    candidates = [f for f in (*CALLER_REFERENCE_FIELDS, "user_id") if f in constraint]
    return max(candidates, key=len) if candidates else None


def _unknown_reference_error(exc: IntegrityError) -> UnknownReferenceError | None:
    """The 422 a foreign key violation deserves, or None when it is not the caller's.

    ``user_id`` is the one reference on this table the caller never supplies — it comes
    from the authenticated token. A violation on it means the account behind a valid
    token is gone, which is a fault on our side; answering 422 would tell the caller to
    fix ids that are all correct and would hide the real problem behind a status that
    pages nobody. Every other reference is theirs, and where the database names which one
    the answer names it too.
    """
    if "foreign key constraint" not in str(exc.orig).lower():
        return None

    field = _violated_reference_field(exc)
    if field is None:
        return UnknownReferenceError(UNKNOWN_REFERENCE_MESSAGE)
    if field not in CALLER_REFERENCE_FIELDS:
        return None
    return UnknownReferenceError(f"This recording points at a {field} that does not exist")


def _is_duplicate_title(exc: IntegrityError) -> bool:
    """Postgres names the violated index; SQLite only names its columns. Everything else
    reaching this commit — the project, genre, subcategory and storyteller foreign keys —
    is not a title conflict and must not be reported as one."""
    detail = str(exc.orig)
    return TITLE_UNIQUE_INDEX in detail or "oc_recordings.title" in detail


async def _ensure_title_available(
    db: AsyncSession,
    project_id: str,
    title: str,
    *,
    exclude_id: str | None = None,
) -> None:
    stmt = select(OC_Recording.id).where(
        OC_Recording.project_id == project_id,
        OC_Recording.title == title,
        OC_Recording.split_from_id.is_(None),
        OC_Recording.splitting_status != SplittingStatus.ARCHIVED_AFTER_SPLIT,
    )
    if exclude_id is not None:
        stmt = stmt.where(OC_Recording.id != exclude_id)
    if (await db.execute(stmt)).first() is not None:
        raise ConflictError(f"A recording titled '{title}' already exists in this project")


async def create_recording(db: AsyncSession, data: RecordingCreate, user_id: str) -> OC_Recording:
    if secondary_equals_primary(
        primary_register_id=data.register_id,
        primary_genre_id=data.genre_id,
        primary_subcategory_id=data.subcategory_id,
        secondary_register_id=data.secondary_register_id,
        secondary_genre_id=data.secondary_genre_id,
        secondary_subcategory_id=data.secondary_subcategory_id,
    ):
        raise SecondaryClassificationConflictError

    title = _normalize_title(data.title)
    if title:
        await _ensure_title_available(db, data.project_id, title)

    if data.storyteller_id:
        await _validate_storyteller_in_project(db, data.storyteller_id, data.project_id)

    recording = OC_Recording(
        project_id=data.project_id,
        genre_id=data.genre_id,
        subcategory_id=data.subcategory_id,
        register_id=data.register_id,
        secondary_genre_id=data.secondary_genre_id,
        secondary_subcategory_id=data.secondary_subcategory_id,
        secondary_register_id=data.secondary_register_id,
        storyteller_id=data.storyteller_id,
        user_id=user_id,
        title=title,
        description=data.description,
        duration_seconds=data.duration_seconds,
        file_size_bytes=data.file_size_bytes,
        format=data.format,
        recorded_at=data.recorded_at,
    )
    db.add(recording)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if (unknown := _unknown_reference_error(exc)) is not None:
            raise unknown from exc
        if not _is_duplicate_title(exc):
            raise
        raise ConflictError(f"A recording titled '{title}' already exists in this project") from exc
    await db.refresh(recording)
    return recording


async def update_recording(
    db: AsyncSession, recording_id: str, data: RecordingUpdate
) -> OC_Recording:

    recording = await get_recording(db, recording_id)
    update_fields = data.model_dump(exclude_unset=True)
    if data.storyteller_id is not None:
        await _validate_storyteller_in_project(db, data.storyteller_id, recording.project_id)
    provided = data.model_fields_set
    effective_register = data.register_id if "register_id" in provided else recording.register_id
    effective_genre = data.genre_id if "genre_id" in provided else recording.genre_id
    effective_sub = (
        data.subcategory_id if "subcategory_id" in provided else recording.subcategory_id
    )
    effective_sec_register = (
        data.secondary_register_id
        if "secondary_register_id" in provided
        else recording.secondary_register_id
    )
    effective_sec_genre = (
        data.secondary_genre_id
        if "secondary_genre_id" in provided
        else recording.secondary_genre_id
    )
    effective_sec_sub = (
        data.secondary_subcategory_id
        if "secondary_subcategory_id" in provided
        else recording.secondary_subcategory_id
    )
    if secondary_equals_primary(
        primary_register_id=effective_register,
        primary_genre_id=effective_genre,
        primary_subcategory_id=effective_sub,
        secondary_register_id=effective_sec_register,
        secondary_genre_id=effective_sec_genre,
        secondary_subcategory_id=effective_sec_sub,
    ):
        raise SecondaryClassificationConflictError
    if data.cleaning_status is not None:
        new_status = data.cleaning_status
        if new_status not in USER_SETTABLE_CLEANING_STATUSES:
            raise InvalidCleaningStatusError(new_status)
    if "title" in update_fields:
        normalized_title = _normalize_title(update_fields["title"])
        if normalized_title and not _is_exempt_from_title_uniqueness(recording):
            await _ensure_title_available(
                db, recording.project_id, normalized_title, exclude_id=recording_id
            )
        update_fields["title"] = normalized_title
    for field, value in update_fields.items():
        setattr(recording, field, value)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        if (unknown := _unknown_reference_error(exc)) is not None:
            raise unknown from exc
        if not _is_duplicate_title(exc):
            raise
        raise ConflictError("A recording with this title already exists in this project") from exc
    await db.refresh(recording)
    return recording


async def _validate_storyteller_in_project(
    db: AsyncSession, storyteller_id: str, project_id: str
) -> None:
    stmt = select(OC_Storyteller).where(OC_Storyteller.id == storyteller_id)
    result = await db.execute(stmt)
    storyteller = result.scalar_one_or_none()
    if storyteller is None:
        raise NotFoundError("Storyteller not found")
    if storyteller.project_id != project_id:
        raise ValidationError("Storyteller does not belong to this project")


async def delete_recording(db: AsyncSession, recording_id: str) -> None:

    recording = await get_recording(db, recording_id)
    if recording.upload_status in ACTIVE_UPLOAD_STATUSES and recording.gcs_url:
        _delete_gcs_blob(recording.gcs_url)
    await db.delete(recording)
    await db.commit()


async def clear_stale_recordings(
    db: AsyncSession,
    project_id: str,
    user_id: str,
    *,
    is_platform_admin: bool = False,
) -> int:
    if not is_platform_admin:
        access_stmt = select(ProjectUserAccess).where(
            ProjectUserAccess.project_id == project_id,
            ProjectUserAccess.user_id == user_id,
            ProjectUserAccess.role == "manager",
        )
        access_result = await db.execute(access_stmt)
        if access_result.scalar_one_or_none() is None:
            raise AuthorizationError("Only a project manager can clear stale recordings")

    stale_statuses = [UploadStatus.UPLOADING, UploadStatus.UPLOAD_FAILED]
    stmt = select(OC_Recording).where(
        OC_Recording.project_id == project_id,
        OC_Recording.upload_status.in_(stale_statuses),
    )
    result = await db.execute(stmt)
    recordings = list(result.scalars().all())

    for recording in recordings:
        if recording.gcs_url:
            _delete_gcs_blob(recording.gcs_url)
        await db.delete(recording)

    await db.commit()
    return len(recordings)


def _gcs_blob_path(project_id: str, genre_id: str, recording_id: str, fmt: str) -> str:

    ext = FORMAT_EXTENSIONS.get(fmt.lower(), f".{fmt.lower()}")
    return f"oral-collector/{project_id}/{genre_id}/{recording_id}{ext}"


async def generate_upload_url(
    db: AsyncSession,
    recording_id: str,
    fmt: str,
    user_id: str,
) -> UploadUrlResponse:

    recording = await get_recording(db, recording_id)
    await check_recording_access(db, recording, user_id)

    blob_path = _gcs_blob_path(recording.project_id, recording.genre_id, recording_id, fmt)

    client = _get_gcs_client()
    bucket = client.bucket(GCS_OC_BUCKET)
    blob = bucket.blob(blob_path)

    ct = content_type_for_format(fmt)

    extra_minutes = (recording.file_size_bytes or 0) // (10 * 1024 * 1024)
    expiry_minutes = min(SIGNED_URL_EXPIRY_MINUTES + extra_minutes, 60)
    expiry = timedelta(minutes=expiry_minutes)

    sa_email, access_token = _get_signing_info()
    upload_url = blob.generate_signed_url(
        version="v4",
        expiration=expiry,
        method="PUT",
        content_type=ct,
        service_account_email=sa_email,
        access_token=access_token,
    )

    expires_at = datetime.now(UTC) + expiry

    recording.upload_status = UploadStatus.UPLOADING
    await db.commit()

    return UploadUrlResponse(
        recording_id=recording_id,
        server_id=recording_id,
        upload_url=upload_url,
        expires_at=expires_at,
        content_type=ct,
    )


async def confirm_upload(
    db: AsyncSession,
    recording_id: str,
    *,
    md5_hash: str | None = None,
    crc32c: str | None = None,
) -> OC_Recording:
    recording = await get_recording(db, recording_id)

    blob_path = _gcs_blob_path(
        recording.project_id,
        recording.genre_id,
        recording_id,
        recording.format,
    )

    payload = UploadConfirmedPayload(
        recording_id=recording_id,
        user_id=recording.user_id,
        expected_blob_path=blob_path,
        expected_size_bytes=recording.file_size_bytes,
        expected_md5_hash=md5_hash,
        expected_crc32c=crc32c,
    )
    await inngest_client.send(
        inngest.Event(name=OCRecordingEvent.UPLOAD_CONFIRMED, data=payload.model_dump())
    )

    return recording


async def generate_resumable_upload_url(
    db: AsyncSession,
    recording_id: str,
    fmt: str,
    user_id: str,
    *,
    origin: str | None = None,
) -> ResumableUploadUrlResponse:
    recording = await get_recording(db, recording_id)
    await check_recording_access(db, recording, user_id)

    blob_path = _gcs_blob_path(recording.project_id, recording.genre_id, recording_id, fmt)

    client = _get_gcs_client()
    bucket = client.bucket(GCS_OC_BUCKET)
    blob = bucket.blob(blob_path)

    ct = content_type_for_format(fmt)
    file_size = recording.file_size_bytes or 0

    session_uri = blob.create_resumable_upload_session(
        content_type=ct,
        size=file_size if file_size > 0 else None,
        origin=origin,
    )

    recording.upload_status = UploadStatus.UPLOADING
    await db.commit()

    return ResumableUploadUrlResponse(
        recording_id=recording_id,
        session_uri=session_uri,
        chunk_size_bytes=RESUMABLE_CHUNK_SIZE,
        content_type=ct,
    )


def _delete_gcs_blob(gcs_url: str) -> None:

    try:
        if not gcs_url.startswith(GCS_PUBLIC_BASE):
            logger.warning("Unexpected GCS URL format: %s", gcs_url)
            return
        blob_name = gcs_url[len(GCS_PUBLIC_BASE) :]
        client = _get_gcs_client()
        bucket = client.bucket(GCS_OC_BUCKET)
        blob = bucket.blob(blob_name)
        blob.delete()
    except Exception:
        logger.exception("Failed to delete GCS blob: %s", gcs_url)
