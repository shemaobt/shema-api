"""The progress history — the append-only trail a year-end ETEN report is rebuilt from.

``docs/shema.md`` §5.2 gives this aggregate one invariant that a service cannot hold alone:
**the entry is produced by the server and never accepted from the client.** The previous
values are the server's own read of the record before the write, so a client that sends them
can rewrite history — and the entry is what ``progressAsOf`` reads to answer *what did this
project look like on that date*, which is what FE-44 §7.8's credit rule counts against. The
table is therefore **append-only in the database**, by the trigger pair in
``app/db/models/shema_enums.py``, not by a rule the second writer has to remember.

One function is the single writer (``applyProgressUpdate``, FE-44 §7.2): it rolls the unit
tables into the aggregates, appends an entry **only if an aggregate changed**, and snapshots
the three tables into the entry. An imported Pulse and a typed update go through it
identically, which is what makes them indistinguishable afterwards.

**The stamp is the actor's local day, and that is why it is a** ``Date`` **and not a
timestamp.** In UTC-3 a save after 21:00 lands on tomorrow's UTC date, and on 31 December in
the next *year* — which is exactly the boundary the ETEN report reconstructs from. The day is
computed where the actor is and stored as the day it was; ``created_at`` beside it is the
moment the row was written and is a different fact.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Boolean, Date, ForeignKey, Index, Integer, String, event, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import guard_append_only
from app.db.types import UtcDateTime


class ShemaProgressEntry(Base):
    """One point in a project's progress, with what it was before and what the tables held.

    The foreign key **restricts** rather than cascading, and the reason is the append-only
    rule one line above it: a cascade would ask the database to delete rows a trigger
    refuses, and the error would name the trigger instead of the project. Restricting says
    the true thing at the right moment — a project with history cannot be deleted, and what
    should happen to the history is a decision the issue that wants a delete endpoint owns.
    There is no such endpoint in wave 1: ``saveProject`` is an upsert and FE-44 §9.3 has no
    ``DELETE``.

    ``created_at`` is stamped from Python as well as from the server, which is not
    redundancy. ``func.now()`` is the transaction's clock — Postgres hands the same
    microsecond to every row written under one commit, and SQLite's ``CURRENT_TIMESTAMP``
    has one-second granularity — so two entries written a moment apart tie, and a trail read
    in the order it happened would come back in an order nobody chose. The sibling's
    ``rr_fund_movements`` records the same finding.

    ``form_type`` is free text on purpose: the values the product writes today are ``full``
    — the prototype's own generator mode — and ``field``, neither of which is a ``FormKind``,
    so typing it as the union rejects the prototype's own value on the first import.
    """

    __tablename__ = "shema_progress_history"
    __table_args__ = (Index("ix_shema_progress_history_project_date", "project_id", "entry_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: The actor's local day, not a UTC one.
    entry_date: Mapped[date] = mapped_column(Date, nullable=False)

    translated_units: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    community_checked_units: Mapped[int] = mapped_column(
        Integer, default=0, server_default=text("0")
    )
    approved_units: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"))
    #: Optional on the contract's entry and nullable here: the roll keeps the previous total
    #: when the tables sum to zero, so an entry that never carried one has none.
    total_units: Mapped[int | None] = mapped_column(Integer, nullable=True)

    #: The snapshot of the three unit tables, which is what makes ``progressAsOf`` a
    #: point-in-time reader rather than a guess.
    book_progress: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    story_progress: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    other_progress: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)

    previous_translated: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_community: Mapped[int | None] = mapped_column(Integer, nullable=True)
    previous_approved: Mapped[int | None] = mapped_column(Integer, nullable=True)

    initial: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    synthetic: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    #: The submitter's name as a string, and together with ``form_type`` the entry's
    #: provenance. A derived notification exists only for an entry that has one.
    from_field: Mapped[str | None] = mapped_column(String(200), nullable=True)
    form_type: Mapped[str | None] = mapped_column(String(60), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


event.listen(ShemaProgressEntry.__table__, "after_create", guard_append_only)
