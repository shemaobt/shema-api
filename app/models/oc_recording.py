from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import CleaningStatus, RecordingSource, SplittingStatus
from app.utils.description_rule import MINIMUM_DESCRIPTION_CLUSTERS, is_sufficient_description

DESCRIPTION_TOO_SHORT = (
    f"description must be at least {MINIMUM_DESCRIPTION_CLUSTERS} characters, counted as "
    "extended grapheme clusters, ignoring leading and trailing whitespace"
)


REFERENCE_NEEDS_EXTERNAL_SOURCE = (
    "source_reference is only meaningful on an external recording; a raw field recording "
    "has no published source to cite"
)


def _reject_insufficient_description(value: str | None) -> str | None:
    """Enforce the ENG-354 threshold on a description the request actually carries.

    Attached as a field validator, so on an update it runs only when the payload mentions
    the field. That is the whole of the grandfathering: there is no migration and no NOT
    NULL, so recordings written before the rule keep short or absent descriptions until
    someone edits that field, and editing anything else about them still works. Explicit
    null is not a way out — it would put a recording back into the state the rule exists
    to prevent.
    """
    if not is_sufficient_description(value):
        raise ValueError(DESCRIPTION_TOO_SHORT)
    return value


class RecordingCreate(BaseModel):
    project_id: str
    genre_id: str
    subcategory_id: str
    register_id: str | None = None
    secondary_genre_id: str | None = None
    secondary_subcategory_id: str | None = None
    secondary_register_id: str | None = None
    storyteller_id: str | None = None
    title: str | None = Field(default=None, max_length=500)
    description: str = Field(max_length=5000)
    duration_seconds: float = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    format: str = Field(min_length=1, max_length=20)
    #: The app never sends this and so writes ``raw``. An importer outside the app says
    #: ``external`` and cites where the audio and its classification came from.
    source: RecordingSource = RecordingSource.RAW
    source_reference: str | None = Field(default=None, max_length=2000)
    recorded_at: datetime

    _check_description = field_validator("description")(_reject_insufficient_description)

    @model_validator(mode="after")
    def _reference_needs_external_source(self) -> "RecordingCreate":
        if self.source_reference is not None and self.source is not RecordingSource.EXTERNAL:
            raise ValueError(REFERENCE_NEEDS_EXTERNAL_SOURCE)
        return self


class RecordingUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    #: Optional but not nullable: omitting it is how a grandfathered recording gets
    #: edited without touching the field, while null is the one value the rule refuses.
    #: The default is never written — the service dumps with `exclude_unset=True`.
    description: str = Field(default="", max_length=5000)
    genre_id: str | None = None
    subcategory_id: str | None = None
    register_id: str | None = None
    secondary_genre_id: str | None = None
    secondary_subcategory_id: str | None = None
    secondary_register_id: str | None = None
    storyteller_id: str | None = None
    duration_seconds: float | None = Field(default=None, ge=0)
    file_size_bytes: int | None = Field(default=None, ge=0)
    cleaning_status: CleaningStatus | None = None
    #: Both optional so an importer can correct a mislabelled row; the app never sends
    #: them. The cross-check here covers a payload that carries both; the service checks
    #: the row as it would be stored when the payload mentions only one of them.
    source: RecordingSource | None = None
    source_reference: str | None = Field(default=None, max_length=2000)

    _check_description = field_validator("description")(_reject_insufficient_description)

    @model_validator(mode="after")
    def _reference_needs_external_source(self) -> "RecordingUpdate":
        if self.source_reference is not None and self.source is RecordingSource.RAW:
            raise ValueError(REFERENCE_NEEDS_EXTERNAL_SOURCE)
        return self


class ReviewFlagResponse(BaseModel):
    """A single review flag on the wire.

    `code` and `origin` are plain strings rather than `ReviewFlagCode` and
    `ReviewFlagOrigin` on purpose. Typing them as the enums would publish a closed set in
    OpenAPI, and a fourth flag code added later would then fail to parse in every client
    generated against today's schema — including the Flutter client of ENG-374, which is
    about to depend on this contract and ships on its own release cycle.
    """

    code: str
    origin: str


class RecordingResponse(BaseModel):
    id: str
    project_id: str
    genre_id: str
    subcategory_id: str
    register_id: str | None = None
    secondary_genre_id: str | None = None
    secondary_subcategory_id: str | None = None
    secondary_register_id: str | None = None
    storyteller_id: str | None = None
    user_id: str | None = None
    title: str | None
    description: str | None = None
    duration_seconds: float
    file_size_bytes: int
    format: str
    gcs_url: str | None
    upload_status: str
    upload_error: str | None = None
    cleaning_status: str
    cleaning_error: str | None = None
    splitting_status: str = SplittingStatus.NONE
    split_from_id: str | None = None
    split_index: int | None = None
    split_segment_count: int | None = None
    review_flags: list[ReviewFlagResponse] = []
    source: str = RecordingSource.RAW
    source_reference: str | None = None
    recorded_at: datetime
    uploaded_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CleaningStatusResponse(BaseModel):
    recording_id: str
    cleaning_status: str
    cleaning_error: str | None = None

    model_config = {"from_attributes": True}


class SplitStatusResponse(BaseModel):
    recording_id: str
    splitting_status: str
    segment_ids: list[str] = []


class UploadUrlRequest(BaseModel):
    recording_id: str
    format: str = Field(min_length=1, max_length=20)


class UploadUrlResponse(BaseModel):
    recording_id: str
    server_id: str
    upload_url: str
    expires_at: datetime
    content_type: str


class ResumableUploadUrlRequest(BaseModel):
    recording_id: str
    format: str = Field(min_length=1, max_length=20)


class ResumableUploadUrlResponse(BaseModel):
    recording_id: str
    session_uri: str
    chunk_size_bytes: int
    content_type: str


class ConfirmUploadRequest(BaseModel):
    md5_hash: str | None = None
    crc32c: str | None = None


class SplitSegment(BaseModel):
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    genre_id: str | None = None
    subcategory_id: str | None = None
    register_id: str | None = None
    gain_db: float | None = None


class SplitRequest(BaseModel):
    segments: list[SplitSegment] = Field(min_length=1)
