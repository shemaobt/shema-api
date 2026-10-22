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


class RecordingSource(StrEnum):
    """Where a recording and everything attached to it came from.

    One mark on the recording covers the audio, its classification and the storyteller it
    points at: those travel together, and a storyteller row is shared by every recording
    of that person, so it is the recording that knows its provenance.

    The app never sends the field and so gets ``RAW``: audio the team captured in the field.
    ``EXTERNAL`` is set only by a caller outside the app, importing from a published source
    such as an archive, and is what tells a reader that the classification on the row was
    not made by whoever sat with the storyteller.
    """

    RAW = "raw"
    EXTERNAL = "external"


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


class SessionState(StrEnum):
    """How a room conversation reads on the Desk's session card (RF-06, ENG-451).

    Not `IRSessionStatus`, which is the room's own machine and is persisted. This is the
    Desk's vocabulary, derived at read time from `ended_at`: `complete` once the floor was
    met, `in_progress` for every other session however long it sat.

    `ABANDONED` stays so the wire vocabulary does not shrink under the Desk, and is never
    emitted: nothing ends a session for being idle (ENG-1263).
    """

    IN_PROGRESS = "in_progress"
    COMPLETE = "complete"
    ABANDONED = "abandoned"


class PhaseStatus(StrEnum):
    """The accepted values of ``project_phases.status``.

    The column is a free ``String(20)`` and stays one, for the reason ``ProjectRole``
    gives: enforcement is at the write path, and rewriting rows a looser code path already
    wrote is not a migration to make blind. What the closed set buys here is the other
    half — declared on ``ProjectPhaseStatusUpdate`` it reaches OpenAPI, so the console
    reads the six values off the contract instead of repeating them, and a seventh is
    added in one place.

    Reads are deliberately **not** coerced through this. ``ProjectPhaseResponse`` and
    ``PhaseStatusLogResponse`` keep ``str`` so a row written before the set was closed
    still renders, and so growing the set does not break clients generated against
    today's schema — the argument ``ReviewFlagResponse`` already makes.
    """

    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    DELAYED = "delayed"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: The three that say the work stopped. A schema cannot state this rule — whether ``note``
#: is required depends on ``status`` — so it lives at the write path with the set itself.
NOTE_REQUIRED_PHASE_STATUSES: frozenset[PhaseStatus] = frozenset(
    {PhaseStatus.DELAYED, PhaseStatus.BLOCKED, PhaseStatus.CANCELLED}
)


class PublicRequestKind(StrEnum):
    CREATE_LANGUAGE = "create_language"
    CREATE_PROJECT = "create_project"


class PublicRequestStatus(StrEnum):
    """The states of ``public_requests.status``, the queue a visitor's request moves through.

    The column stays a ``String(20)`` and enforcement is at the write path, as with the other
    machines here. ``PENDING`` is where a request is born and is never a verdict, which is why
    the review payload narrows this to a ``Literal`` of the two a reviewer may stamp instead of
    accepting the whole enum.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
