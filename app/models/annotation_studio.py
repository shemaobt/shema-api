"""Pydantic schemas for the annotation-studio app module.

Ported from the studio's ``interface/schemas/{catalog,tiers,export}.py``.
The tripod ``LanguageResponse`` (``app.models.language``) is reused for the
language picker; ``AsLanguageSummary`` adds per-language readiness for the
studio dashboard. ``is_seed`` is intentionally dropped — tripod languages are
``{id, name, code, created_at}``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PresignedUpload(BaseModel):
    """A single signed PUT target, returned by the GCS storage adapter."""

    url: str
    method: str
    storage_key: str
    required_headers: dict[str, str]
    expires_in: int


class UploadTicket(BaseModel):
    storage_key: str
    upload_url: str
    method: str
    required_headers: dict[str, str]
    expires_in: int

    @classmethod
    def from_presigned(cls, presigned: PresignedUpload) -> UploadTicket:
        return cls(
            storage_key=presigned.storage_key,
            upload_url=presigned.url,
            method=presigned.method,
            required_headers=presigned.required_headers,
            expires_in=presigned.expires_in,
        )


# ── Catalog: languages (dashboard summary) + speakers ──────────────────────


class AsLanguageSummary(BaseModel):
    """A tripod language that has studio data, with collection readiness."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    created_at: datetime
    readiness: dict


class LanguageMemberResponse(BaseModel):
    """A facilitator granted access to a specific language (admin views)."""

    user_id: str
    email: str
    display_name: str | None = None
    created_at: datetime


class LanguageMemberCreate(BaseModel):
    email: str


class SpeakerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    label: str
    display_name: str | None = None


class SpeakerCreate(BaseModel):
    label: str | None = None
    display_name: str | None = None


class SpeakerUpdate(BaseModel):
    display_name: str | None = None


# ── Tier A: words + reference audio + recordings ───────────────────────────


class WordCreate(BaseModel):
    gloss: str | None = None
    emblem: str | None = None


class WordUpdate(BaseModel):
    gloss: str | None = None
    emblem: str | None = None


class WordReferenceCreate(BaseModel):
    upload_format: str


class WordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    label: str
    gloss: str | None = None
    emblem: str | None = None
    reference_key: str | None = None


class TierARecordingCreate(BaseModel):
    speaker_id: str
    rep_index: int
    upload_format: str
    duration_ms: int | None = None


class TierARecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    word_id: str
    speaker_id: str
    rep_index: int
    export_filename: str
    upload_status: str
    storage_key: str


class TierARecordingTicket(BaseModel):
    recording: TierARecordingResponse
    upload: UploadTicket


# ── Tier B: minimal pairs + recordings ─────────────────────────────────────


class PairCreate(BaseModel):
    pair_number: int
    word_a_text: str | None = None
    word_b_text: str | None = None
    speaker_id: str | None = None


class PairUpdate(BaseModel):
    word_a_text: str | None = None
    word_b_text: str | None = None


class PairResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    pair_number: int
    word_a_text: str | None = None
    word_b_text: str | None = None
    speaker_id: str | None = None


class TierBRecordingCreate(BaseModel):
    side: str
    rep_index: int
    upload_format: str
    duration_ms: int | None = None


class TierBRecordingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    pair_id: str
    side: str
    rep_index: int
    export_filename: str
    upload_status: str
    storage_key: str


class TierBRecordingTicket(BaseModel):
    recording: TierBRecordingResponse
    upload: UploadTicket


# ── Tier C: clips + free-sort assignments ──────────────────────────────────


class ClipCreate(BaseModel):
    clip_number: int
    upload_format: str
    source_recording_id: str | None = None
    source_word_text: str | None = None
    position: str | None = None
    duration_ms: int | None = None


class ClipResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    clip_number: int
    export_clip_id: str
    position: str | None = None
    upload_status: str
    storage_key: str


class ClipTicket(BaseModel):
    clip: ClipResponse
    upload: UploadTicket


class SortAssignmentRequest(BaseModel):
    dimension: str
    round: str = "normal"
    group_label: str | None = None


class SortAssignmentResponse(BaseModel):
    clip_id: str
    export_clip_id: str
    dimension: str
    round: str
    group_label: str | None = None


class ReliabilityResponse(BaseModel):
    dimension: str
    n_compared: int
    agreement_pct: float | None = None


# ── Export bundles + analysis results ──────────────────────────────────────


class ExportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    language_id: str
    status: str
    tiers_included: str | None = None
    size_bytes: int | None = None
    created_at: datetime


class ExportDetail(ExportResponse):
    manifest: dict | None = None
    download_path: str | None = None


class ResultCreate(BaseModel):
    export_id: str | None = None
    results_json: dict


class ResultResponse(BaseModel):
    id: str
    language_id: str
    export_id: str | None = None
    recommended_layer: int | None = None
    tiers: str | None = None
    created_at: datetime
    plots: dict[str, str] = {}


class PlotPresignRequest(BaseModel):
    name: str
    content_type: str = "image/png"


class PlotPresignResponse(BaseModel):
    storage_key: str
    upload_url: str
    method: str
    required_headers: dict[str, str]
    expires_in: int
