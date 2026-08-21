import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class IRPromptKey(enum.StrEnum):
    GUIDE = "guide"
    VALIDATOR = "validator"
    COVERAGE_CLASSIFIER = "coverage_classifier"
    BOOK_PANORAMA = "book_panorama"
    DRAFT_SELF_CHECK = "draft_self_check"
    BT_ANALYST = "bt_analyst"
    BT_VERDICT_SPEAKER = "bt_verdict_speaker"


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
    after_panorama: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    prepared_speech: Mapped[str | None] = mapped_column(Text, nullable=True)
    prepared_audio_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    coverage_state: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    kept_takes: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    back_translation: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    #: Whose conversation this was. Null when the room app did not identify itself with a
    #: device credential, which is every session until ENG-454 ships that half — see the
    #: migration notes. Not a foreign key, matching the column it stands beside on
    #: ``ir_takes``: the room tables carry ids across an app boundary and have never
    #: constrained them.
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
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
        DateTime(timezone=True),
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
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
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heard_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Whose conversation this was. Null when the room app did not identify itself with a
    #: device credential, which is every session until ENG-454 ships that half — see the
    #: migration notes. Not a foreign key, matching the column it stands beside on
    #: ``ir_takes``: the room tables carry ids across an app boundary and have never
    #: constrained them.
    project_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


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
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
