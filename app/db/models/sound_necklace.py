"""Sound-necklace session tables.

A session is a facilitator's pass over one recorded story. It carries the grid
parameters the SPA needs to reopen the audio, its lifecycle status, and — in a
dedicated narrow table — the state document the SPA autosaves.

The enums live here, not with the DTOs that expose them: the database constrains
each to exactly these values, so a value change has to arrive with a migration.
Portuguese survives only inside the state document, which is the SPA's and is
never interpreted here.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class SessionStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class SessionStep(enum.StrEnum):
    LISTEN = "listen"
    CUT = "cut"
    TRIAGE = "triage"
    PHRASES = "phrases"
    CONVERSATION = "conversation"
    SAVE = "save"


class GranularityLevel(enum.StrEnum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


class ConsentType(enum.StrEnum):
    """Which consent a record attests to.

    Both values exist from the first migration, and the second one is not speculation:
    §12 requires recorded consent PER SPEAKER, and the Colar records two people. The
    story is one of them; the listener is the other, and the app captures 21+ recordings
    of their voice (§8.7). Adding the value later would mean an ``ALTER TYPE`` on the
    database six production apps share, to say something already known today.
    """

    # The facilitator attests that the story may be processed by the pipeline.
    PIPELINE_USE = "pipeline_use"
    # The listener consents to their own voice being recorded and processed. They never
    # hold an account (they may not read at all), so ``confirmed_by`` names the
    # facilitator who witnessed it — the witness, never the subject.
    VOICE_ANSWERS = "voice_answers"


class AuditEvent(enum.StrEnum):
    """What was recorded (§12).

    Every URL name says ISSUED, and that is the whole of what this API can honestly
    claim. The bytes are served by storage against a short-lived signed URL and never
    pass through here, so a download is something it never witnesses: the URL may be used
    once, ten times, shared, or never opened. An ``audio_downloaded`` would be a lie the
    next reader would build a retention or a breach report on.

    ``ARTIFACT_UPLOADED`` is the only event here that claims a transfer, and those bytes
    really do come through the API. It is not the only upload that does — a voice answer is
    also posted through it — but that one is the listener recording their own voice, and
    §14 forbids logging the listener working. Reaching for a voice already recorded is the
    facilitator action §12 asks about; making one is not.
    """

    AUDIO_URL_ISSUED = "audio_url_issued"
    ARTIFACT_UPLOADED = "artifact_uploaded"
    ARTIFACT_URL_ISSUED = "artifact_url_issued"
    VOICE_URL_ISSUED = "voice_url_issued"
    SESSION_COMPLETED = "session_completed"
    SESSION_REOPENED = "session_reopened"
    CONSENT_RECORDED = "consent_recorded"


class ArtifactKind(enum.StrEnum):
    """Which of the three artifacts. The stored FILENAMES stay Portuguese
    (``manifesto-contas.json``, ``retorno-ancoragem.json``,
    ``relatorio-mapeamento.md``): PRD §10 freezes them as part of the contract shared
    with the downstream pipeline. The kind is the handle, not the file."""

    MANIFEST = "manifest"
    ANCHORING = "anchoring"
    REPORT = "report"


# `values_callable` makes the database store the value ("in_progress"), not the
# member name ("IN_PROGRESS") — the values are what goes on the wire.
_STATUS_TYPE = Enum(
    SessionStatus,
    name="sn_session_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_ARTIFACT_KIND_TYPE = Enum(
    ArtifactKind,
    name="sn_artifact_kind_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_STEP_TYPE = Enum(
    SessionStep,
    name="sn_session_step_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_GRANULARITY_TYPE = Enum(
    GranularityLevel,
    name="sn_granularity_level_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_CONSENT_TYPE = Enum(
    ConsentType,
    name="sn_consent_type_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_AUDIT_EVENT_TYPE = Enum(
    AuditEvent,
    name="sn_audit_event_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class SnSession(Base):
    """One facilitator's pass over one recorded story.

    ``audio_ref`` is a real foreign key rather than a remembered string, and that is
    load-bearing: it is the only link from a bucket audio to the artifacts cut from it,
    so a session naming an audio nobody has would be an export nothing could ever trace
    back — the row would survive and the one field saying where it came from would be
    wrong. NO ACTION on delete, never CASCADE: removing an audio must fail while a
    session points at it, because the alternative is destroying somebody's finished work
    to satisfy a delete they did not ask for. Deleting the PROJECT still works, since
    both rows cascade from it in the same statement. Its width matches
    ``sn_audio_refs.audio_id``; a wider column could hold a value the referenced one
    cannot store.
    """

    __tablename__ = "sn_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    audio_ref: Mapped[str] = mapped_column(
        String(128), ForeignKey("sn_audio_refs.audio_id"), index=True
    )
    story_name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    manifest_id: Mapped[str] = mapped_column(String(64))
    granularity_level: Mapped[GranularityLevel] = mapped_column(_GRANULARITY_TYPE)
    bead_sec: Mapped[float] = mapped_column(Float)
    pipeline_consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[SessionStatus] = mapped_column(_STATUS_TYPE, default=SessionStatus.IN_PROGRESS)
    # The station the saved state was left at. Completion displays as `guardar`
    # without overwriting this, so reopening restores the real station.
    current_step: Mapped[SessionStep] = mapped_column(_STEP_TYPE, default=SessionStep.LISTEN)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The advisory single-editor lease. Null is unheld, which is why it lives here
    # rather than in a table of its own: a lock row per session would have to be
    # upserted into existence on every acquire, and there is no upsert that spells the
    # same on Postgres and on the SQLite the tests run against.
    # SET NULL, never CASCADE: a holder is not an owner. Nothing sweeps lapsed leases, so
    # this column keeps naming whoever last opened the session — and under CASCADE,
    # deleting that user would take the session, its state and its artifacts with it.
    # Null is already the right end state for a deleted holder: unheld.
    locked_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # Expiry is decided on read; nothing sweeps lapsed leases. A crashed tab therefore
    # frees its session without anyone unlocking it by hand.
    lock_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # The session's accumulated net working time, as a whole count of seconds: a plain
    # Integer, never Interval — see working_time, which argues that and does the
    # accumulating.
    net_working_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # The instant the last counted heartbeat was stamped, and the cursor the accumulation
    # compare-and-swaps on. Null means "no stretch to measure from": completing a session
    # clears it, so the first heartbeat after a reopen charges nothing at all and the
    # closed stretch is never counted, however short it was.
    last_working_tick_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class SnSessionState(Base):
    """The SPA's autosaved state document, held verbatim.

    ``state`` is TEXT and never JSON: the document is built and re-validated by the
    client under a strict schema, so it is stored as the exact bytes that arrived —
    a JSON column would discard key order and whitespace and the API must never
    re-shape a document it does not own. ``version`` backs the autosave
    compare-and-swap. The row is created with the session and stays empty until the
    first autosave.
    """

    __tablename__ = "sn_session_state"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SnSessionTick(Base):
    """One "still here" heartbeat, and nothing else about it.

    The whole table is deliberately impoverished. There is one event — the session was
    open and the tab was visible — carrying no idea of what was clicked, typed, played or
    looked at, because §14 forbids telemetry on listener behaviour and a schema with room
    for it is the first step across that line. Session metadata is what is allowed here,
    and a session metadata table with a ``what_happened`` column would not stay one.

    Append-only while the session is open, and dropped when it completes. The total on
    ``sn_sessions`` is derived from these rows rather than the other way round, so keeping
    them is what makes it auditable while it can still move; a lone counter could only
    ever be believed. Completion freezes the total, and from that moment the rows would
    record nothing but when the facilitator was at their desk.

    ``occurred_at`` is the database's own clock, never the client's and never the
    application's; ``working_time`` is where that choice is argued.

    ``client_tick_id`` exists only so a retried or twice-delivered heartbeat cannot be
    charged twice. It is the client's own opaque string and means nothing here beyond
    "the same beat"; the unique constraint with the session is what makes the replay a
    no-op rather than a second gap. Scoped to the session rather than global because it
    is minted per session by a client that has no idea what other sessions exist.
    """

    __tablename__ = "sn_session_ticks"

    # The unique constraint is also the only index this table needs. The duplicate check
    # looks up exactly this pair, and the delete on completion looks up by session alone —
    # the leading column of that same index. Nothing reads the beats in time order on any
    # hot path — the running total is kept on the session — and an index per heartbeat
    # insert that no query reads is a cost paid all session long for nothing.
    __table_args__ = (
        UniqueConstraint("session_id", "client_tick_id", name="uq_sn_session_ticks_session_client"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="CASCADE")
    )
    client_tick_id: Mapped[str] = mapped_column(String(64))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnArtifact(Base):
    """One of a session's three exported artifacts, held as an opaque object.

    The bytes are NOT here. They live in GCS, exactly as the SPA produced them, and
    this row is the queryable pointer plus the checksums that prove custody. A Postgres
    column would be a trap either way: ``jsonb`` discards key order, whitespace and
    duplicate keys, and even ``text`` invites something downstream to re-encode it. The
    pipeline diffs these files byte for byte against a golden reference (PRD §10.5), so
    the API's only job is to hand back what it was given.

    ``crc32c`` is the checksum GCS itself validated on the way in — a corrupt upload is
    rejected by storage and the object is never created. ``sha256`` is ours, for an
    audit trail that does not depend on trusting the storage provider.

    Keyed by (session, kind): a session has at most one artifact of each kind, and
    re-completing a reopened session replaces it rather than accumulating versions the
    pipeline would then have to choose between.
    """

    __tablename__ = "sn_artifacts"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[ArtifactKind] = mapped_column(_ARTIFACT_KIND_TYPE, primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column(Integer)
    crc32c: Mapped[str] = mapped_column(String(16))
    sha256: Mapped[str] = mapped_column(String(64))
    content_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SnVoiceAnswer(Base):
    """One spoken Mapeamento answer, kept by the question it answers.

    Like the artifacts, the bytes are not here — they are a WebM/Opus object in the
    private bucket, and this row is the queryable pointer. The listing is what tells the
    Mapeamento screen which questions already have an answer, which is why the answers
    are a table and not just a bucket prefix: a prefix listing is an extra GCS round trip
    and cannot be joined or scoped in one query.

    ``resource_path`` is the logical, contract-frozen path the SPA builds
    (``respostas/level{1,2,3}/…/<k>.webm``, §10.4) — validated against a fixed allowlist
    before it is ever used, so it can be trusted as the object-name suffix. Keyed by
    (session, path): one file per question (O5), and re-recording replaces in place.
    """

    __tablename__ = "sn_voice_answers"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    resource_path: Mapped[str] = mapped_column(String(255), primary_key=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    size: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class SnConsent(Base):
    """One consent, recorded as evidence of a lawful basis (§12 / O6).

    This row is the authoritative evidence. ``sn_sessions.pipeline_consent`` predates it
    and is write-only — the SPA sends it on create and then reads its own copy out of the
    state document; no response has ever carried it. ``record_consent`` keeps it in step
    so the two cannot contradict each other, but it is not a source of truth: read this.

    The table holds consents that were GIVEN — there is no row meaning "refused". Absent,
    denied and granted are three different things, and only the last one is a consent, so
    silence is left as silence rather than written down as a false.

    Keyed by (session, type), so re-confirming updates the record instead of stacking a
    second one: the question it answers is "is this consent held, and as of when",
    which has one answer per session and type.

    ``confirmed_at`` is set in Python, never by ``onupdate``. A re-confirmation changes
    no other column, so the ORM would emit no UPDATE at all and the timestamp would
    quietly keep the first confirmation's time — a record that misdates itself is worse
    than no record.

    The oral form §12 admits — a consent audio for a speaker who cannot sign — is a
    nullable column on this table, which is the cheap ALTER-later case. It ships with the
    route that fills it, not before: there is no upload route and no screen that records
    one yet, so a column now would be a shape to migrate around, not evidence.
    """

    __tablename__ = "sn_consents"

    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="CASCADE"), primary_key=True
    )
    type: Mapped[ConsentType] = mapped_column(_CONSENT_TYPE, primary_key=True)
    # SET NULL, never CASCADE: the account that typed the confirmation is not the record.
    # A second facilitator can re-confirm a consent on somebody else's session, and under
    # CASCADE deleting that account would erase the evidence while the session itself
    # stands — proof gone with nothing to explain its absence. Null says the honest thing:
    # this consent was confirmed by an account that no longer exists. RESTRICT is not the
    # answer either; `users` is shared with every other Tripod app, and a consent row here
    # must not be what makes deleting a user fail over there.
    confirmed_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SnAuditEvent(Base):
    """One recorded reach for protected material (§12).

    Append-only by nature: nothing updates a row here, because an event is a thing that
    happened. Written in the same transaction as the operation it records, so there is
    never a signed URL issued without a row to say so — and if the database is unreachable
    the route has already failed at its own read, long before there is anything to log.

    ``project_id`` is carried rather than joined through the session: an audio is reached
    before any session exists over it, and the log's whole purpose is to be queryable per
    project.

    ``resource_ref`` is the LOGICAL reference — the part of the resource's key that is not
    the session (``audio_id``, the artifact kind, the answer's respostas/… path) — not the
    storage key. Three reasons, in order: the audio's object name lives in a ``Text``
    column with no bound at all and would overflow anything declared here; an artifact's
    storage key is content-addressed, so it changes under a re-upload and a stale key would
    read as a different file; and the logical ref is what a person auditing this actually
    recognises. (session_id, resource_ref) is the resource's identity, exactly as its own
    table keys it. The longest value is an ``audio_id`` at 128 — not the voice path, which
    its allowlist bounds at 93 — and 128 is a measured number: a Terena pilot slug once
    hit 83 and forced that column from 64 to 128 (20260713_0001).

    ``ip`` stays null. This runs on Cloud Run, behind a proxy: ``request.client.host`` is
    the proxy's address, and the client end of ``X-Forwarded-For`` is appended to whatever
    the caller sent, so it is forgeable. Both would put a number in an evidence log that
    reads like a fact and is not one. The column exists because adding it later means a
    migration on a database six production apps share; filling it needs a trusted-proxy
    policy, which is its own work.
    """

    __tablename__ = "sn_audit_events"

    __table_args__ = (
        Index("ix_sn_audit_events_project_occurred", "project_id", "occurred_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # SET NULL, never CASCADE: deleting a user must not erase the record of what that
    # account reached. That is the one question an audit log exists to answer, and an
    # account being gone is when it is asked most.
    user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event: Mapped[AuditEvent] = mapped_column(_AUDIT_EVENT_TYPE)
    # Nullable: an audio is reached outside any session.
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sn_sessions.id", ondelete="SET NULL"), nullable=True
    )
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE")
    )
    resource_ref: Mapped[str] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45), nullable=True)


class SnAudioRef(Base):
    """The audios of one project's bucket.

    An acousteme artifact is standalone by design — it carries no project, no
    recording, and its ``audio_id`` is a caller-minted slug rather than a foreign key
    (``oc_acousteme_artifacts``). This row is what gives such an audio a project, and
    that is the whole of its job: without it there is nothing for a project gate to
    stand on, and the audios would only be reachable through the Oral Collector's own
    routes, which have no project scoping at all.

    ``consent_present`` is the collection consent of §12/O6. It is recorded here rather
    than derived: the consent a storyteller gave at recording time lives in
    ``oc_storytellers`` and is reachable only from a recording, which a pilot audio does
    not have. It defaults to False — an unrecorded consent is an absent one, never an
    assumed one.

    One project per audio, mirroring ``oc_recordings``. Sharing one audio across
    projects would widen the key, and nothing asks for that.
    """

    __tablename__ = "sn_audio_refs"

    # Matches oc_acousteme_artifacts.audio_id, which this joins to by convention and
    # not by constraint — the acousteme table is deliberately free of foreign keys.
    audio_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    consent_present: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TranscriptStatus(enum.StrEnum):
    """Where one answer's draft is. There is no ``running``: a claimed-but-unfinished
    state survives a crashed worker as a row nothing will ever move again, and the cure
    (a sweeper, or a heartbeat column) costs more than the disease. A lost worker leaves
    ``pending``, which the next trigger simply picks up."""

    PENDING = "pending"
    READY = "ready"
    FAILED = "failed"


_TRANSCRIPT_STATUS_TYPE = Enum(
    TranscriptStatus,
    name="sn_transcript_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class SnAnswerTranscript(Base):
    """The transcription (and English translation) draft of one voice answer.

    Advisory only. Nothing here is ever merged into an artifact by the API — a human
    confirms the draft in the SPA, and an unconfirmed draft never leaves (PRD v2 §1.1,
    §12). That is also why the text lives in its own table rather than in the answer
    row: the recording is evidence, the draft is a suggestion about it, and ``force``
    throws the suggestion away without touching the evidence.

    These rows ARE the job's state — there is no job table. ``pending`` is work to do,
    ``ready`` is work never to pay for twice, ``failed`` carries its own reason and
    blocks nothing else.

    The key is the answer's, and the foreign key is composite ON DELETE CASCADE: delete
    or re-record an answer and its draft goes with it, with no cleanup code to forget.

    ``language`` is the interview language the answer was spoken in, as the SPA sends it on
    the trigger: it is the transcriber's hint and the switch that decides whether a
    translation is needed. ``generation`` backs the compare-and-swap that keeps a pass in
    flight from writing its result over a draft a ``force`` has already reset.

    Two transcripts, not one. ``transcript_source`` is the cleaned text — what the
    facilitator reads and confirms — and ``transcript_verbatim`` is what speech-to-text
    returned before the disfluency cleanup touched it. Keeping both is what makes the
    removal inspectable: a human cannot be the last word on a sentence they were never
    shown, and without the verbatim column the only record of a dropped sentence would be
    the model call that dropped it.

    Equality between the two does NOT mean the cleanup failed. A cleanup that fell back to
    verbatim produces equal texts, and so does a successful cleanup of an answer that had no
    hesitation in it — equality is the one signal that cannot tell those apart. Selecting
    ``WHERE transcript_verbatim = transcript_source`` and ``force``-ing the result would
    re-bill the transcription of every cleanly-processed answer in the session and throw
    away drafts a facilitator had already confirmed.
    """

    __tablename__ = "sn_answer_transcripts"

    session_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    resource_path: Mapped[str] = mapped_column(String(255), primary_key=True)
    status: Mapped[TranscriptStatus] = mapped_column(
        _TRANSCRIPT_STATUS_TYPE, default=TranscriptStatus.PENDING
    )
    language: Mapped[str] = mapped_column(String(16))
    generation: Mapped[int] = mapped_column(Integer, default=0)
    transcript_verbatim: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_source: Mapped[str | None] = mapped_column(Text, nullable=True)
    translation_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        ForeignKeyConstraint(
            ["session_id", "resource_path"],
            ["sn_voice_answers.session_id", "sn_voice_answers.resource_path"],
            ondelete="CASCADE",
        ),
    )


class SnProjectSettings(Base):
    """The bead granularity a project cuts at — one row, one decision, one grid.

    ``beadSec`` is the coordinate system the downstream pipeline and the training data
    are built on: it defines the bead grid and is mixed into ``manifest_id``. Choosing it
    per session, as the SPA's setup screen used to, let two audios of one project land on
    two incompatible grids. It is a property of the project, so it lives on the project.

    ``bead_sec`` is nullable and is NOT what the admin sets. The admin sets a LEVEL; the
    resolved duration is ``granularity_frames[level] * hop_sec``, which comes from each
    audio's own acousteme (the O8 rule) and so is not known until an audio is cut. The
    first session on the project stamps it here, and from then on it is the value every
    later audio has to agree with — the SPA refuses one whose acousteme would resolve
    differently rather than cutting it on a second grid.

    The row IS the lock. ``granularity_level`` is NOT NULL, so a row existing means an
    admin confirmed a level, and confirming is what freezes it — the settings screen says
    as much on the button before the write happens. That is not caution, it is the only
    arrangement where the invariant holds: a level that could move afterwards would either
    contradict the ``bead_sec`` a session already stamped — leaving the project unable to
    open another session at all — or split the corpus across two grids, which is the exact
    thing this table exists to prevent. Re-cutting a project at a new granularity means
    re-deriving every ``manifest_id`` it has already exported, and that is a migration,
    not a setting.

    ``updated_by`` is SET NULL, never CASCADE: the account that chose the granularity is
    not the setting, so deleting that user must not take a project's grid with it, and
    RESTRICT would make a row here the reason a user cannot be deleted in an app that
    shares this database.
    """

    __tablename__ = "sn_project_settings"

    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    granularity_level: Mapped[GranularityLevel] = mapped_column(_GRANULARITY_TYPE)
    bead_sec: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
