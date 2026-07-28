from enum import StrEnum


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
