"""The health assessment — its own aggregate, and the source the record's flat fields project.

``docs/shema.md`` §5.3 is emphatic about the shape because the sibling module got the
equivalent one wrong once: the four dimensions, the date, the assessor and the note that sit
on ``shema_projects`` are a **projection of the newest entry here**, never a second truth.
BE-07 appends and re-projects in one step, and carries a pre-history record into the history
before appending so that a first assessment cannot erase what the flat fields already held.

**The per-dimension note is the data; the running note is a reading of it.** ``compileNotes``
derives ``notes`` from ``dimension_notes`` at write time so the older display keeps working —
one source, one derivation. A server that stores only the blob has lost the data and cannot
get it back.

**NULL is *not assessed*, and it is not** ``boa``. All 127 seed records arrive with every
dimension empty, so unassessed is the dominant state rather than an edge case, and
``isAssessed`` — *at least one dimension is rated* — is what gates everything that counts an
assessment, including Rhythm's readiness. A ``health_assessment_date`` with four unrated
dimensions would otherwise report a team as heard when nobody rated it.

**BE-07 added three columns and the reason is one sentence each.**
``question_set_version`` is which guiding questions the ratings answered, because the questions
are provisional (FE-37) and an answer to a question nobody can quote is not interpretable.
``created_by`` and ``created_by_name`` are the author — *who entered the row*, which is not the
same person as the ``assessor`` who read the team. The attribute docstrings carry the
arguments.

**Nothing in this module ever updates or deletes a row here**, which is the immutability the
issue asks for and is a property of the write path rather than of a trigger:
``app/services/shema/append_assessment.py`` is the only writer, it only ever inserts, and there
is no route that edits or removes an assessment. The trigger stays off for the reason the class
docstring gives — a mentor's typo is a person's to correct, and the issue that builds that
correction needs the door this table deliberately leaves open.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import HEALTH_LEVEL, ShemaHealthLevel
from app.db.types import UtcDateTime


class ShemaHealthAssessment(Base):
    """One assessment of one project, by one mentor, on one day.

    This table is **not** append-only, unlike ``shema_progress_history`` beside it, and the
    difference is deliberate rather than an oversight. ``docs/shema.md`` §7.2 names exactly
    two database-level invariants in this module — the progress trail and the org chart's
    audit row — and this is neither: an assessment is a person's reading that a person may
    correct, while a progress entry is a derived record of what the counts were and the
    audit row is an accountability fact about somebody else. Making it append-only would
    turn a typo in a mentor's note into a permanent second row.

    The foreign key cascades, for the same reason the progress history's restricts: there is
    nothing here that outlives the project it assesses, and no trail to strand.

    ``app/db/models/project_health.py`` is a different product and shares nothing with this
    — an AI interview engine that stores project and team as free text and is not even FK'd
    to ``projects``. ``docs/shema.md`` §4.8 is the verdict and ``CLAUDE.md`` §3.2 warns
    against the conflation by name.
    """

    __tablename__ = "shema_health_assessments"
    __table_args__ = (
        Index("ix_shema_health_assessments_project_date", "project_id", "assessment_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    #: The mentor's name as it was then, not a user reference: this is a record of who read
    #: the team, and a rename does not change who did the reading.
    assessor: Mapped[str] = mapped_column(String(200), default="", server_default="")

    emotional: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    relational: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    spiritual: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)
    physical: Mapped[ShemaHealthLevel | None] = mapped_column(HEALTH_LEVEL, nullable=True)

    #: ``{emotional?, relational?, spiritual?, physical?}`` — the data.
    dimension_notes: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    #: Derived from ``dimension_notes`` at write time, kept so the older display works.
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    #: Which published set of guiding questions these ratings answered
    #: (``app/utils/shema_health_questions.py``). **NULL is not version 1.**
    #:
    #: The guiding questions are provisional until FE-37 settles them, so the wording a mentor
    #: read is part of what their rating means — and the day it changes, a row that does not
    #: say which set it answered is an answer to a question nobody can quote. Every appended
    #: row carries one.
    #:
    #: NULL is the third state and it is the honest one: the entry BE-07 carries forward out of
    #: the record's flat fields, which came from a Notion column rather than from a
    #: questionnaire. Stamping it ``1`` would assert that somebody was asked version 1's four
    #: questions, which nobody was. ``docs/shema.md`` §7.4's two absences are the same shape —
    #: an ORM default here would manufacture provenance.
    question_set_version: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: Who filed the row, and the name as it was then — the pair ``shema_record_edits`` keeps,
    #: for its reason.
    #:
    #: Distinct from :attr:`assessor`, and the two are not redundant: ``assessor`` is *who read
    #: the team* and is a field of the reading, while this is *who entered it* and is an
    #: accountability fact about an account. A mentor's visit typed up by the regional
    #: coordinator is one row with two different people in it, and collapsing them would lose
    #: whichever of the two the next reader needed.
    #:
    #: ``RESTRICT`` rather than ``SET NULL``, as the edit trail does: this is the record of who
    #: entered a reading of a team, and an account that carries one cannot be deleted out from
    #: under it. The name beside it is the copy that stays readable years later, and it is
    #: ``''`` — never an invented stand-in — for the carried-forward entry whose author is
    #: genuinely unknown.
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

    #: Stamped from Python as well as from the server, and that is not redundancy.
    #: ``func.now()`` is the transaction's clock — Postgres hands the same microsecond to every
    #: row of one commit and SQLite's ``CURRENT_TIMESTAMP`` has one-second granularity — so the
    #: two rows one submission can write (the carried-forward entry and the new one) would tie,
    #: and the history would come back in an order nobody chose. ``shema_progress_history``
    #: records the same finding beside this table.
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
