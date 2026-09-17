from pydantic import BaseModel


class UploadConfirmedPayload(BaseModel):
    recording_id: str
    user_id: str | None = None
    expected_blob_path: str
    expected_size_bytes: int
    expected_md5_hash: str | None = None
    expected_crc32c: str | None = None


class CleanRequestedPayload(BaseModel):
    recording_id: str
    user_id: str
    gcs_url: str


class SplitSegmentData(BaseModel):
    start_seconds: float
    end_seconds: float
    genre_id: str
    subcategory_id: str
    register_id: str | None = None
    gain_db: float | None = None


class SplitRequestedPayload(BaseModel):
    """Snapshot of the parent recording at split-request time. Consumers MUST
    treat these values as authoritative and not refetch the parent — both
    because Inngest replays the event on retry (refetching would be
    non-idempotent), and because the snapshot is frozen at request time so
    any updates to the parent between request and persist are intentionally
    not reflected in child segments (ENG-64).
    """

    recording_id: str
    user_id: str
    segments: list[SplitSegmentData]
    project_id: str
    format: str
    title: str
    recorded_at: str
    description: str | None = None
    storyteller_id: str | None = None
    secondary_genre_id: str | None = None
    secondary_subcategory_id: str | None = None
    secondary_register_id: str | None = None


class BlobVerificationResult(BaseModel):
    size: int


class SegmentResult(BaseModel):
    id: str
    gcs_url: str
    duration_seconds: float
    file_size_bytes: int
    index: int


class TranscriptionRequestedPayload(BaseModel):
    """A session whose answers need drafts.

    The session id and nothing else: the work to do is whatever is `pending` in
    `sn_answer_transcripts` when the run starts, so a replayed event never redoes a draft
    and never carries a stale copy of one.
    """

    session_id: str
