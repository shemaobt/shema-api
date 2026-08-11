"""Pydantic schemas for the sound-necklace app module.

The wire contract the SPA generates its TypeScript types from (code-first
OpenAPI). Provisional: the resources not yet implemented are stubs returning 501, so
every schema is tagged ``x-stability: experimental`` and mirrors the SPA's provisional
contracts (sound-necklace ``contracts/``). Artifacts and the session-state envelope are
opaque — never parsed or re-serialized here.

Where this and the SPA's provisional contracts disagree, this wins and the SPA
regenerates: its ``contracts/bucket.ts`` still types the codebook version as an integer
and the audio duration as non-null, and both are wrong against the pipeline that
actually mints them (ENG-261).
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.exceptions import (
    ERROR_CODE_CONFLICT,
    ERROR_CODE_PROJECT_GRANULARITY_LOCKED,
    ERROR_CODE_SESSION_LOCK_CHANGED,
    ERROR_CODE_SESSION_LOCKED,
)
from app.db.models.sound_necklace import (
    ArtifactKind,
    AuditEvent,
    ConsentType,
    GranularityLevel,
    SessionStatus,
    SessionStep,
    TranscriptStatus,
)

# Vendor extension marking every schema in this module as provisional.
_EXPERIMENTAL: dict[str, Any] = {"x-stability": "experimental"}


# ── Enums ───────────────────────────────────────────────────────────────────
#
# Every enum here is imported from the db model rather than defined here: they all
# back real columns, and the database constrains each to exactly these values. Keeping
# them with the table is what forces a value change to come with a migration.


# ── Artifacts ───────────────────────────────────────────────────────────────
#
# Bytes are uploaded raw (multipart) and served back verbatim from storage: they
# never enter a Pydantic model, so nothing can re-shape them. Only this envelope
# is typed.


class ArtifactResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    kind: ArtifactKind
    size: int
    # Both checksums the API recorded, so a consumer can verify a fetched artifact
    # against what was stored rather than trusting the transfer. crc32c is what GCS
    # validates on the way in; sha256 is ours, provider-independent.
    crc32c: str
    sha256: str


# ── Sessions ────────────────────────────────────────────────────────────────

MANIFEST_ID_PATTERN = r"^fnv1a32:[0-9a-f]{8}$"


class SessionProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    current_step: SessionStep


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    id: str
    project_id: str
    story_name: str
    story_slug: str
    status: SessionStatus
    last_modified: str
    progress: SessionProgress


class SessionListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    sessions: list[SessionSummary]


class SessionCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    # The text lengths mirror their columns: unbounded here, an over-long value would
    # reach Postgres and fail the insert instead of failing validation.
    audio_id: str = Field(max_length=128)
    project_id: str
    story_name: str = Field(max_length=255)
    story_slug: str = Field(max_length=255)
    granularity_level: GranularityLevel
    bead_sec: float = Field(gt=0)
    manifest_id: str = Field(pattern=MANIFEST_ID_PATTERN)
    pipeline_consent: bool


class SessionStateUpdate(BaseModel):
    """Autosave body: opaque session-state envelope; only the version is read."""

    model_config = ConfigDict(extra="allow", json_schema_extra=_EXPERIMENTAL)

    schema_version: int


class AutosaveResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    saved_at: str
    schema_version: int


# ── Advisory single-editor lock ──────────────────────────────────────────────


class LockHolder(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    user_id: str
    display_name: str


class LockStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    held: bool
    holder: LockHolder | None = None
    expires_at: str | None = None


class SessionLockedResponse(BaseModel):
    """The 409 of a write refused while somebody else holds the editor lock.

    `code` is what the client branches on and the other two are what it renders, so this
    is a contract and not a debug body — hence a model the SPA can generate types from
    rather than a description in prose.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    detail: str
    code: Literal["SESSION_LOCKED"] = ERROR_CODE_SESSION_LOCKED
    holder_name: str
    expires_at: str


class SessionLockChangedResponse(BaseModel):
    """The 409 of a write the lease refused and then lapsed on. Retry; no holder to show."""

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    detail: str
    code: Literal["SESSION_LOCK_CHANGED"] = ERROR_CODE_SESSION_LOCK_CHANGED


# ── Voice-answer resources (canonical respostas/... path) ────────────────────

# The logical, contract-frozen path the SPA builds for each answer (§10.4). It is an
# allowlist, not a hint: the three shapes are all that can name an object, which is what
# lets the path be trusted as an object-name suffix — no traversal, no free-form key.
#
# The segments are LENGTH-BOUNDED, and that bound is load-bearing, not cosmetic. The path
# is used verbatim as the object-name suffix and stored in a VARCHAR(255); an unbounded k
# would pass validation, upload the bytes to the private bucket, then fail the INSERT on
# Postgres — a 500 with an LGPD-sensitive recording orphaned where the API can't reach
# it. The question keys are short human-authored strings, so 64 is generous.
RESOURCE_PATH_PATTERN = (
    r"^respostas/(level1/[a-z0-9_]{1,64}"
    r"|level2/PT[1-9][0-9]{0,3}/[a-z0-9_]{1,64}"
    r"|level3/P[1-9][0-9]{0,3}/[a-z0-9_]{1,64})\.webm$"
)


class ResourceSummary(BaseModel):
    """One recorded answer in the listing — the path is what the Mapeamento screen keys
    on to know which questions are answered."""

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    path: str
    size: int


class ResourceListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    resources: list[ResourceSummary]


class ResourceUrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    url: str


# ── Consent records (§12 / O6) ───────────────────────────────────────────────


class ConsentCreate(BaseModel):
    """Record a consent. Which one is the whole body: who confirmed it is the caller,
    and when is now — neither is the client's to assert."""

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    type: ConsentType


class ConsentResponse(BaseModel):
    """One consent record — the evidence, as stored.

    ``confirmed_by`` is nullable because the record outlives the account that typed it:
    a deleted user leaves the consent standing and its confirmer null. It names whoever
    OPERATED the app, which for ``voice_answers`` is the facilitator who witnessed the
    listener — the listener never holds an account.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    type: ConsentType
    confirmed_by: str | None = None
    confirmed_at: str


class ConsentListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    consents: list[ConsentResponse]


# ── Audit log (§12) ──────────────────────────────────────────────────────────


class AuditEventResponse(BaseModel):
    """One recorded reach, as stored.

    Every field is nullable exactly where the row is: constraints on a RESPONSE model are
    assertions the framework enforces on the way out, and one unlucky row would 500 the
    whole listing — in the one place whose job is to still answer when things went wrong.

    ``ip`` is on the table but not here. Nothing writes it yet (behind Cloud Run's proxy
    there is no address this API can honestly attribute to the caller), and a response
    field is additive — it can join the day something fills the column, without breaking
    the SPA. Shipping it now would only generate an ``ip: string | null`` the SPA might
    build a screen column for, forever null.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    id: str
    occurred_at: str
    event: AuditEvent
    user_id: str | None = None
    session_id: str | None = None
    resource_ref: str


class AuditListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    events: list[AuditEventResponse]


# ── Bucket audios ─────────────────────────────────────────────────────────────


class AcoustemeEnvelope(BaseModel):
    """The granularity grid an audio's bead duration is derived from.

    ``beadSec = granularity_frames[level] x hop_sec`` — the two fields exist together
    or the envelope is useless, so an audio whose grid is incomplete carries no
    envelope at all rather than half of one.

    ``codebook_version`` is a string, not a number: it is half of the acousteme
    artifact's primary key and reads like ``terena-xlsr53-k100-v1``. An integer here
    would be a version the pipeline never mints.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    codebook_version: str
    hop_sec: float
    granularity_frames: dict[str, int]


class BucketAudioResponse(BaseModel):
    """An audio the facilitator can pick from the project's bucket.

    ``acousteme`` is null when no servable grid exists for the audio — an ingest that
    never succeeded, or an audio that was never tokenized. That is a fallback, not an
    error (PRD §6.1: the levels then map to fixed durations), so the audio still lists.

    ``duration_sec`` is nullable because response models are validated on the way
    out: one un-probed audio would otherwise fail validation of the whole listing.
    The invariant belongs at ingestion, where a violation is actionable.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    id: str
    filename: str
    duration_sec: float | None = None
    consent_present: bool
    acousteme: AcoustemeEnvelope | None = None


class BucketAudioListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    audios: list[BucketAudioResponse]


class AudioUrlResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    url: str


# ── Transcription drafts (ENG-325) ───────────────────────────────────────────


class TranscriptionRequest(BaseModel):
    """Start (or restart) the drafts for a session's recorded answers.

    ``language`` is the interview language, and it is the client's to say: the session
    row does not carry one, and the SPA is what knows which language the questions were
    asked in. It is a hint for the transcriber and the switch that decides whether a
    translation is needed at all.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    #: BCP-47 locale (`pt-BR`, `en-US`).
    language: str = Field(min_length=2, max_length=16)
    #: Throw the existing drafts away and transcribe again — the re-record case.
    force: bool = False
    #: Which answers ``force`` applies to. Omitted (or null) means the whole session,
    #: which is what the report's own trigger still asks for. Naming the re-recorded
    #: answer is what keeps one repeated take from costing a whole session of
    #: transcriptions.
    paths: list[str] | None = None


class AnswerTranscript(BaseModel):
    """One answer's draft. Advisory: nothing here reaches an artifact unconfirmed.

    ``translation_en`` carries the English text whatever the interview language was — for
    an English interview it is the transcript itself — so the report reads one field.
    ``error`` is the answer's own failure, and it never means the job failed.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    path: str
    status: TranscriptStatus
    transcript_source: str | None = None
    translation_en: str | None = None
    error: str | None = None
    #: The draft's revision counter, which the confirm route takes back as its guard.
    #: Required, not defaulted: an optional field in the generated types invites the client
    #: to fill a missing one in with 0, which is a valid-looking confirm the guard refuses
    #: and no reload can fix.
    generation: int


class TranscriptionProgressResponse(BaseModel):
    """What the SPA polls while the report is open."""

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    total: int
    ready: int
    failed: int
    pending: int
    answers: list[AnswerTranscript]


class TranscriptConfirmRequest(BaseModel):
    """A transcript as a human confirmed it, once they had corrected it (ENG-394).

    Only the spoken-language text is sent. The English is never the client's to state: it
    is re-derived here from what was confirmed, which is the whole point of the route —
    the report reads the English field, so a correction the client alone applied would
    never reach it.

    ``generation`` is the counter the client last read for this answer, and it makes the
    confirm a compare-and-swap: a facilitator whose draft was re-transcribed underneath
    them is refused rather than allowed to write an edit of text that no longer exists.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    #: The spoken-language text as the human confirmed it. Bounded at both ends: an empty
    #: confirm would store a ``ready`` draft with two blank text fields, which on screen is
    #: an answer nobody transcribed, and the text is forwarded verbatim to a billed model,
    #: so the ceiling is a cost limit as much as a validation one. 20k characters is far
    #: past the longest answer a single question produces.
    transcript_source: str = Field(min_length=1, max_length=20_000)
    generation: int = Field(ge=0)

    @field_validator("transcript_source")
    @classmethod
    def _must_carry_speech(cls, value: str) -> str:
        """Refuse a confirm with nothing in it, and store everything else verbatim.

        ``min_length`` alone lets a run of spaces through, which stores a ``ready`` draft
        whose text is blank on screen — indistinguishable from an answer nobody
        transcribed, and unlike a real one it carries no ``error`` to explain itself.

        The value comes back unchanged rather than stripped. What is rejected here is an
        empty confirm, not a badly spaced one, and a human's confirmed text is theirs.
        """
        if not value.strip():
            raise ValueError("transcript_source must contain more than whitespace")
        return value


class TranscriptConfirmConflictResponse(BaseModel):
    """The 409 of a confirm sent from a draft that has since been rewritten.

    A third arm next to the two lock 409s, and it has to be its own model for the reason
    those two are separate from each other: the client branches on ``code``, and this one
    demands the opposite reaction to SESSION_LOCK_CHANGED. Retrying this unchanged replays
    the same stale generation forever — the only way out is to re-read the draft.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    detail: str
    code: Literal["CONFLICT"] = ERROR_CODE_CONFLICT


# ── Project settings (ENG-352) ───────────────────────────────────────────────


class ProjectSettingsResponse(BaseModel):
    """The project's bead granularity, as every screen reads it.

    Both values are nullable and mean different things when absent. A null
    ``granularity_level`` is a project nobody has configured yet — the setup screen
    renders that as "not decided", never as an error. A null ``bead_sec`` is a project
    that has not cut anything yet, so no audio has a grid to agree with.

    ``locked`` is derived, not stored: it says the project's level has been confirmed,
    and confirming is what freezes it — no session needs to exist. The client needs it to
    decide whether the settings screen offers a control or an explanation, and deriving it
    there would make every screen fetch what the server already knows.
    """

    model_config = ConfigDict(from_attributes=True, json_schema_extra=_EXPERIMENTAL)

    project_id: str
    granularity_level: GranularityLevel | None = None
    bead_sec: float | None = None
    locked: bool = False
    updated_at: str | None = None


class ProjectSettingsUpdate(BaseModel):
    """What a project admin decides: a LEVEL, and nothing else.

    ``bead_sec`` is deliberately not settable. It is ``granularity_frames[level] *
    hop_sec`` off each audio's own acousteme (the O8 rule), so a client that sent one
    would be asserting a grid rather than resolving it — and a wrong assertion here is
    a corpus cut on two coordinate systems. The project's first session stamps it.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    granularity_level: GranularityLevel


class ProjectGranularityLockedResponse(BaseModel):
    """The 409 the PUT answers with once the project has cut something."""

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    detail: str
    code: Literal["PROJECT_GRANULARITY_LOCKED"] = ERROR_CODE_PROJECT_GRANULARITY_LOCKED


# ── Net working time (ENG-396) ───────────────────────────────────────────────


class WorkingTimeTick(BaseModel):
    """One "still here" heartbeat. Deliberately the smallest thing that can be sent.

    No timestamp, because the server stamps it and a client clock is not a time source
    an accumulating counter can trust. No description of what the facilitator was doing,
    because §14 forbids telemetry on listener behaviour and a field for it here is where
    that would start.

    ``client_tick_id`` is the client's own identifier for the beat, and exists only so a
    retried or twice-delivered one is not charged twice.

    It is pinned to a UUID rather than left as free text, and that is a privacy control
    rather than tidiness. A free-form string this API stores verbatim and forever is
    somewhere a later client could thread ``"cut;played=3;bead=17"`` — per-interaction
    telemetry smuggled through an idempotency key, arriving in the one table whose whole
    claim is that it records nothing about what was done. The pattern constrains that
    rather than preventing it: 122 bits of hex is ample room to encode something, so what
    this really does is make smuggling deliberate and obvious instead of casual. Anyone
    who wants the guarantee has to read the clients, not this field.

    The pattern fixes the length at 36, so no separate bound is declared: a second one
    would only be a number to keep in step with the regex.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    client_tick_id: str = Field(
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    )


class WorkingTimeResponse(BaseModel):
    """The session's accumulated net working time, in whole seconds.

    Seconds rather than a duration string: the SPA already formats this number for
    display and a second unit on the wire would be a second thing to keep in step.

    Served on every tick and on demand, with no rule about when to look at it — the SPA
    shows it on completion and not before, and that stays the SPA's decision.
    """

    model_config = ConfigDict(json_schema_extra=_EXPERIMENTAL)

    net_working_seconds: int
