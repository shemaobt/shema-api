from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import CleaningStatus, SplittingStatus


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
    description: str | None = Field(default=None, max_length=5000)
    duration_seconds: float = Field(ge=0)
    file_size_bytes: int = Field(ge=0)
    format: str = Field(min_length=1, max_length=20)
    recorded_at: datetime


class RecordingUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
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
