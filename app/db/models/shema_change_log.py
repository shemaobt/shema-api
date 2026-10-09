"""The change log — who did what to which part of the PME, and when, without saying to what.

OBT-577 — Karina, via Daniel, 6/out/2026: *"toda alteração seja gravada, datada e com o nome de
quem alterou."* ``shema_record_edits`` already answers that for the project's own fields, and
the ledgers beside it answer it for a seat (``shema_role_changes``), a region
(``shema_scope_changes``) and a health assessment. What was left were the writes that changed a
row and kept no author — an intercessor edited, a member removed, a meeting log undone, a
link revoked — and this table is for them. One row is one act: the person, the day, the subject
and the verb.

**It records no value, by construction and not by filter.** :attr:`field_keys` names the fields
an act moved and the table has no column that could hold what they moved to. The edit trail
(``ShemaRecordEdit``) stores both sides of a field and has to withhold the guarded ones; this
one is for acts whose subject is a person's contact or a prayer request, and a log that never
held the value is a log that cannot leak it to a reader who is not allowed the record.

**No foreign key on the account or the project.** The table is append-only through the
module's trigger, which refuses UPDATE and DELETE, and ``SET NULL`` and ``CASCADE`` are one
each (``ShemaScopeChange`` made the same argument). The actor's name is stamped as it was then.
"""

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import Index, String, Text, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import guard_append_only
from app.db.types import UtcDateTime


class ChangeSubject(enum.StrEnum):
    """What an act was done to. The closed set the writers draw from; the column is text."""

    INTERCESSOR = "intercessor"
    MEETING = "meeting"
    ETEN_CREDIT = "eten_credit"
    INTAKE_LINK = "intake_link"
    SUBMISSION = "submission"
    PENDING_PROJECT = "pending_project"
    MEDIA = "media"


class ChangeAction(enum.StrEnum):
    """What was done."""

    CREATED = "created"
    UPDATED = "updated"
    REMOVED = "removed"
    REVIEWED = "reviewed"
    REPLACED = "replaced"
    CONSENT_RECORDED = "consent-recorded"
    CONSENT_WITHDRAWN = "consent-withdrawn"
    REVOKED = "revoked"
    IMPORTED = "imported"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class ShemaChangeLog(Base):
    """One act on the PME by one person, with the keys of what it touched."""

    __tablename__ = "shema_change_log"
    __table_args__ = (
        Index("ix_shema_change_log_occurred_at", "occurred_at"),
        Index("ix_shema_change_log_project", "project_id", "occurred_at"),
        Index("ix_shema_change_log_region", "region_key", "occurred_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    #: A :class:`ChangeSubject`.
    subject: Mapped[str] = mapped_column(String(40), nullable=False)
    subject_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: A :class:`ChangeAction`.
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    #: The project the act belongs to, when it belongs to one; the reader's scope is decided by it.
    project_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #: The region the act belongs to, when it has no project (a meeting's region, an intercessor's).
    region_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    #: JSON array of the keys the act moved. Keys, never values.
    field_keys: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: The account, when there was one: the intake link and the exit link are unauthenticated.
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Python's clock and not the server's, ``shema_progress_history``'s choice and for its
    #: reason: each row is its own event, and a tie between two acts in one second would leave the
    #: feed to order them by a random id.
    occurred_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), default=lambda: datetime.now(UTC), server_default=func.now()
    )


event.listen(ShemaChangeLog.__table__, "after_create", guard_append_only)
