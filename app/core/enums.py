from enum import StrEnum


class ProjectRole(StrEnum):
    """The accepted values of ``project_user_access.role``.

    The column is a free ``String(30)`` and stays one: enforcement is at the write path,
    not in the database. A CHECK constraint would have to be reconciled against whatever
    production rows already hold, and rewriting somebody's data to fit a new enum is not
    a migration to make blind.

    That leaves one gap worth being precise about, because it decides which way this
    fails. A row written by an older code path or by direct SQL can still hold anything.
    Every read asks for ``FACILITATOR`` exactly, so an unrecognised value **denies**. The
    column can be wrong; it cannot be wrong in the direction that grants.
    """

    MEMBER = "member"
    MANAGER = "manager"
    #: Serves a team on the Facilitator Desk. Narrower than access: a member or a manager
    #: of the same project is not one, and neither is someone who reaches the project
    #: through an organization. Granted by administration, outside this product.
    FACILITATOR = "facilitator"


class UploadStatus(StrEnum):
    LOCAL = "local"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    VERIFIED = "verified"
    UPLOAD_FAILED = "upload_failed"


ACTIVE_UPLOAD_STATUSES: list[str] = [UploadStatus.UPLOADED, UploadStatus.VERIFIED]


class CleaningStatus(StrEnum):
    NONE = "none"
    NEEDS_CLEANING = "needs_cleaning"
    CLEANING = "cleaning"
    CLEANED = "cleaned"
    FAILED = "failed"


USER_SETTABLE_CLEANING_STATUSES: frozenset[CleaningStatus] = frozenset(
    {CleaningStatus.NONE, CleaningStatus.NEEDS_CLEANING}
)


class SplittingStatus(StrEnum):
    NONE = "none"
    SPLITTING = "splitting"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED_AFTER_SPLIT = "archived_after_split"


class ReviewFlagCode(StrEnum):
    MISSING_CLASSIFICATION = "missing_classification"
    INSUFFICIENT_DESCRIPTION = "insufficient_description"
    MISSING_STORYTELLER = "missing_storyteller"


class ReviewFlagOrigin(StrEnum):
    SYSTEM = "system"


class AcoustemeStatus(StrEnum):
    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


class OCRecordingEvent(StrEnum):
    UPLOAD_CONFIRMED = "oc/recording.upload-confirmed"
    CLEAN_REQUESTED = "oc/recording.clean-requested"
    SPLIT_REQUESTED = "oc/recording.split-requested"


class SnTranscriptionEvent(StrEnum):
    REQUESTED = "sn/transcription.requested"


class OCNotificationEvent(StrEnum):
    UPLOAD_VERIFIED = "oc.upload.verified"
    UPLOAD_FAILED = "oc.upload.failed"
    CLEANING_COMPLETED = "oc.cleaning.completed"
    CLEANING_FAILED = "oc.cleaning.failed"
    SPLIT_COMPLETED = "oc.split.completed"
    SPLIT_FAILED = "oc.split.failed"
