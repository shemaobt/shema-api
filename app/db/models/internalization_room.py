import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Enum, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class IRPromptKey(enum.StrEnum):
    GUIDE = "guide"
    VALIDATOR = "validator"
    COVERAGE_CLASSIFIER = "coverage_classifier"
    BOOK_PANORAMA = "book_panorama"
    DRAFT_SELF_CHECK = "draft_self_check"
    BT_ANALYST = "bt_analyst"
    BT_VERDICT_SPEAKER = "bt_verdict_speaker"
    COMPREHENSION_ASSESSOR = "comprehension_assessor"


class IRSessionStatus(enum.StrEnum):
    IN_PROGRESS = "in_progress"
    DONE = "done"
    NEEDS_PERSON = "needs_person"


_PROMPT_KEY_TYPE = Enum(
    IRPromptKey,
    name="ir_prompt_key_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)
_SESSION_STATUS_TYPE = Enum(
    IRSessionStatus,
    name="ir_session_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class IRSession(Base):
    __tablename__ = "ir_sessions"
    __table_args__ = (Index("ix_ir_sessions_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pericope: Mapped[str] = mapped_column(String(120))
    status: Mapped[IRSessionStatus] = mapped_column(
        _SESSION_STATUS_TYPE, default=IRSessionStatus.IN_PROGRESS
    )
    messages: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    #: Whether this session was opened straight after the book's panorama, which is how the
    #: guide knows not to introduce itself twice. It is also the only record that a team
    #: heard the panorama and went on into this passage — the panorama's own row names the
    #: book and no passage — so ``panorama_once`` reads it to decide whether to play it again.
    after_panorama: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    prepared_speech: Mapped[str | None] = mapped_column(Text, nullable=True)
    prepared_audio_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    #: Which passage the prepared opening above was written from. Null while nothing is
    #: prepared, and null on every row written before ENG-450.
    #:
    #: It exists because the guard that stops one passage's opening being spoken as another's
    #: cannot be derived. It used to compare the opening against ``DEFAULT_PERICOPE`` and
    #: worked only because one constant stood in both places. Re-resolving at hand-over time
    #: looks equivalent and is not: if another device of the same team closes the passage
    #: while the panorama is still playing, the resolution moves, both sides agree on the new
    #: passage, and the line written from the old one is handed over as the new one's own
    #: framing — to people who cannot read and cannot check.
    prepared_pericope: Mapped[str | None] = mapped_column(String(120), nullable=True)
    coverage_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    kept_takes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    back_translation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Whose conversation this was. Null when the room app did not identify itself with a
    #: device credential, which is every session until ENG-454 ships that half — see the
    #: migration notes. Not a foreign key, matching the column it stands beside on
    #: ``ir_takes``: the room tables carry ids across an app boundary and have never
    #: constrained them.
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    #: When the conversation ended, stamped only where an end actually happened — the
    #: completion floor closing the session. A session nobody closed is not stamped here:
    #: its end is derived from its last activity at read time, because the idle limit that
    #: decides it is a proposal shared with the room app (ENG-435) and not yet agreed, and a
    #: number nobody has agreed must not be frozen into rows. ``session_end.end_of`` is the
    #: whole of the rule.
    ended_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    bridge_mode: Mapped[str] = mapped_column(
        String(24), default="calibration_pending", server_default="calibration_pending"
    )
    #: Which language the room speaks to this team, chosen by the tablet when the session
    #: opened and never afterwards. A per-request choice would let the room change language
    #: underneath a team because somebody changed a phone setting mid-passage, and half a
    #: passage in each language is worse than the whole of it in either.
    #:
    #: Not ``Project.language_id``. That column records the team's own language for the rest
    #: of the platform and the room does not read it: the device decides, because the device
    #: is what the facilitator set up in front of them.
    language: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    #: Declared with the ``server_default`` its own migration already writes. The model said
    #: only ``default=dict``, which is Python-side and never reaches the DDL, so a table built
    #: from the metadata got a NOT NULL column with no default and any insert that did not
    #: name it failed. On `main` nothing inserted into ``ir_sessions`` without the ORM, so the
    #: gap was invisible there; the migration round-trip cases on this branch do exactly that.
    comprehension: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IRCoverageEvent(Base):
    """One step a session moved one bead forward.

    ``ir_sessions.coverage_state`` stays the fast read of where a necklace stands; this is
    how it got there. A row is written only when a merge actually changes an element, so
    the table grows with transitions and not with turns — the classifier runs after every
    turn and mostly reports beads that are already where it says.

    ``project_id`` and ``pericope`` are copied off the session instead of joined for.
    Element keys come from the canon: ``being:B3`` is Naomi in every project that works
    this passage, and the same key repeats across the passages she appears in. A key alone
    therefore does not name a bead, and the question the Desk asks of this table — which
    session touched this one last — needs all three in one index to be a single lookup.

    ``status`` holds the plain ``CoverageStatus`` value that ``coverage_state`` already
    stores. A database enum here would give one scale two spellings, and a type to migrate
    on both sides every time the scale grows a step.

    That a session reaches a given status on a given bead once is the rule the service
    keeps, and deliberately not a unique constraint. Two turns overlapping is ordinary —
    the classifier for one turn is still on its round trip when the next lands, and each
    settle runs in its own transaction — so both can read the same tracker and write the
    same step. A constraint would refuse the second one and take that whole transaction
    with it, losing the beads only the later settle heard: the merge would fail at the one
    moment ``furthest`` was written for. A repeated row costs a row; the reconstruction
    takes the furthest status per bead and cannot see it.

    ``at`` is stamped in the application rather than by the database. On PostgreSQL
    ``now()`` is the transaction's clock, so every event of one settle would carry the same
    instant, and the order beads moved in — the thing this table exists to remember —
    would be gone.
    """

    __tablename__ = "ir_coverage_events"
    __table_args__ = (
        Index("ix_ir_coverage_events_step", "session_id", "element_key", "status"),
        Index(
            "ix_ir_coverage_events_element_touched",
            "project_id",
            "pericope",
            "element_key",
            "at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36))
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pericope: Mapped[str] = mapped_column(String(120))
    element_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(32))
    at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
    )


class IRPrompt(Base):
    __tablename__ = "ir_prompts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    key: Mapped[IRPromptKey] = mapped_column(_PROMPT_KEY_TYPE, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    prompt: Mapped[str] = mapped_column(Text)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class IRQuestionStatus(enum.StrEnum):
    OPEN = "open"
    ANSWERED = "answered"
    RESOLVED = "resolved"


_QUESTION_STATUS_TYPE = Enum(
    IRQuestionStatus,
    name="ir_question_status_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class IRQuestion(Base):
    """A question the team raised by the hand, addressed to a person rather than the app.

    It belongs to the device, not to the session it was asked in. A facilitator may answer
    hours later, long after that passage is closed, and the team must still receive it —
    otherwise the necklace shows a knot for a question that went nowhere.
    """

    __tablename__ = "ir_questions"
    __table_args__ = (Index("ix_ir_questions_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    session_id: Mapped[str] = mapped_column(String(36))
    pericope: Mapped[str] = mapped_column(String(120))
    audio_key: Mapped[str] = mapped_column(String(512))
    #: Which bead of the Meaning Map the hand went up on, as the app names it. Nullable
    #: because every row written before ENG-447 has none, and because the app only starts
    #: sending it with ENG-456 — a card that names no element is the common case today,
    #: not a broken one.
    element_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: How long the recording runs, measured from the audio at ingest and never taken from
    #: the client. Nullable because the measurement is a call to a tool outside this
    #: process: when it is missing the card shows audio with no length, which is worth more
    #: than an ingest that refuses the question.
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: What was said, **for the facilitator alone**. It makes the inbox skimmable and the
    #: set of them is the log of questions the Meaning Map could not answer. It must never
    #: reach the team's app — transcribing the team's voice *for the team* is out of scope
    #: for v1 — and `tests/test_ir_transcript_stays_with_the_facilitator.py` holds that line
    #: over the whole set of room routes rather than over any one of them. Nullable for the
    #: same reason as the duration: a provider outage does not lose a question.
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[IRQuestionStatus] = mapped_column(
        _QUESTION_STATUS_TYPE, default=IRQuestionStatus.OPEN
    )
    reply_audio_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    answered_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    heard_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    #: Whose conversation this was. Null when the room app did not identify itself with a
    #: device credential, which is every session until ENG-454 ships that half — see the
    #: migration notes. Not a foreign key, matching the column it stands beside on
    #: ``ir_takes``: the room tables carry ids across an app boundary and have never
    #: constrained them.
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )


class IRTakeKind(enum.StrEnum):
    ENSAIO = "ensaio"
    RETRO = "retro"


_TAKE_KIND_TYPE = Enum(
    IRTakeKind,
    name="ir_take_kind_enum",
    values_callable=lambda enum_cls: [m.value for m in enum_cls],
)


class IRTake(Base):
    """Audio the team recorded that is the work itself, not a means to a transcript.

    The conversation's audio is thrown away once it has been heard — the record there is the
    text. These two are different: the ensaio take is the passage as the team tells it, and
    the back-translation chunks are what a reviewer would need to hear to check the telling.
    Losing them loses the session.

    `project_id` is whose work this is. It was called `team_id` and held nothing; the rest
    of the schema says "project" for the same entity, and carrying two words for one thing
    is how the next person loses an afternoon. "Team" stays the Desk's word, in the UI and
    in the backlog.
    """

    __tablename__ = "ir_takes"
    __table_args__ = (
        UniqueConstraint("session_id", "storage_key", name="uq_ir_takes_session_storage_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    device_id: Mapped[str] = mapped_column(String(64), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    pericope: Mapped[str] = mapped_column(String(120))
    kind: Mapped[IRTakeKind] = mapped_column(_TAKE_KIND_TYPE)
    scope: Mapped[str] = mapped_column(String(120))
    pass_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    chunk_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64))
    crc32c: Mapped[str] = mapped_column(String(16))
    content_type: Mapped[str] = mapped_column(String(64))
    verified_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )


class IRSegment(Base):
    """One stretch of a rehearsal recording, as a thing with its own address.

    A stretch used to be a line in the JSON list on ``ir_sessions.back_translation``, so the
    only way to name one was its position in that list. Everything that follows from
    correcting a single stretch — which recording explains it, which slice of that recording,
    which version counts, what it was divided out of — had nowhere to live.

    **The slice is ``(take_id, starts_ms, ends_ms)``, and the two times are relative to that
    one file.** Never global over the concatenated passage: it is the globalness, not the use
    of intervals, that made re-recording one stretch shift every stretch after it. Relative to
    an immutable file they never shift, and subdividing becomes writing rows rather than
    cutting audio — which is what lets the room do it with no connection.

    ``take_id`` is the mother tongue; ``bridge_take_id`` and ``transcript`` are the team's own
    explanation of it in Portuguese, which is the only transcript that exists. The two travel
    together or not at all: a new version of the native audio is born with neither, because
    correcting only the native does not exist as a product state.

    A version is a new row for the same position, not an edit in place. ``superseded_at`` is
    what stops counting; ``superseded_by_id`` is what took its place, and it is null when the
    stretch was abandoned rather than replaced — which is what starting a telling-back over
    does to every stretch of a session at once. Two facts, and the second one does not always
    exist, so one column could not carry both.

    No foreign keys, matching ``ir_takes``, ``ir_questions`` and ``ir_coverage_events``: the
    room tables carry ids across an app boundary and have never constrained them, and one
    table with a different rule is how the next person loses an afternoon.

    There are two partial unique indexes and the second is not redundant: a unique index
    treats NULLs as distinct, so the one naming ``parent_id`` enforces nothing at all for a
    stretch nobody divided — which is most of them. Measured on the migration's own database
    rather than assumed.
    """

    __tablename__ = "ir_segments"
    __table_args__ = (
        Index("ix_ir_segments_session_current", "session_id", "superseded_at"),
        Index(
            "uq_ir_segments_position",
            "session_id",
            "parent_id",
            "ordinal",
            unique=True,
            postgresql_where=text("superseded_at IS NULL"),
            sqlite_where=text("superseded_at IS NULL"),
        ),
        Index(
            "uq_ir_segments_root_position",
            "session_id",
            "ordinal",
            unique=True,
            postgresql_where=text("superseded_at IS NULL AND parent_id IS NULL"),
            sqlite_where=text("superseded_at IS NULL AND parent_id IS NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), index=True)
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    #: Which stretch this one was divided out of. Null for a stretch nobody divided.
    parent_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    #: Where it sits among its own siblings, 1-based. Position among the children of one
    #: parent, or among the session's undivided stretches — never a number over the whole
    #: session, so dividing one stretch renumbers nothing outside it.
    ordinal: Mapped[int] = mapped_column(Integer)
    take_id: Mapped[str] = mapped_column(String(36), index=True)
    starts_ms: Mapped[int] = mapped_column(Integer)
    ends_ms: Mapped[int] = mapped_column(Integer)
    #: 1 for the first telling of a stretch, 2 when it was told again after a finding. Carried
    #: unchanged from the JSON it replaces because the Refine artifact labels pass-1/pass-2 and
    #: something downstream reads it. Under versions-as-rows a retell is arguably a new version
    #: of the telling rather than a second pass, but that is F7's argument to have, not a
    #: contract to change in the same diff that redefines the address.
    pass_number: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    bridge_take_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(
        UtcDateTime(timezone=True), nullable=True
    )
    superseded_by_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
