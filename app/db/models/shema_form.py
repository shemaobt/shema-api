"""Received submissions and the leader's intake link — the module's two unauthenticated seams.

``docs/shema.md`` §5.12 and FE-44 §5.7 settle what these hold before GATE-03 settles the file
format. Four of the rules are not open and are built on here: the import is **idempotent and
transactional** so a double import is a no-op, the submission is archived **byte-identically**,
**only the Pulse is archivable**, and the leader link grants the intake form and nothing else
and it expires.

**Only the Pulse is archivable — which is why there is no ``kind`` column.** ``ArchivedKind``
is ``"pulso"`` and deliberately narrower than ``FormKind``: the Avaliação de Saúde is filled
in-app and produces no file, so nothing of it ever leaves to come back, and its history
belongs to ``shema_health_assessments``. A column with one value would invite a second, and a
server that archives a ``health`` submission has landed a kind that by definition never left.
A table with no such column cannot hold one.

**The token is stored hashed**, following every other token in this repository —
``refresh_tokens``, ``password_reset_tokens`` and ``access_invites`` all keep a ``String(64)``
hash and let the raw value leave exactly once. ``docs/shema.md`` §6.6 adds the rule that
matters more than the storage: the guard is a **service function**, ``verify_intake_token``,
not a router condition, so it holds for any future caller of it.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaSubmission(Base):
    """One received Pulse, and the file it arrived as.

    ``language_name`` and ``submitted_by`` are **snapshots on the row**, because the contract
    puts them on ``ReceivedSubmission`` and because an archive that resolves them through the
    project would answer with today's values for a file received last year. That is the
    opposite of the *never duplicate a role-holder's name* rule and for the same reason: this
    is a record of what arrived, not a view of what is.

    ``storage_key`` is the archived artifact, byte-identical to what was submitted, in the
    module's private bucket. ``content_hash`` is what makes the import idempotent without a
    read of the file: a second arrival of the same bytes for the same project conflicts on
    the unique index rather than producing a second archive and a second progress entry.

    The project reference **restricts**: an archive whose project was deleted is an archive
    nobody can read, and what should happen to received files is a decision the issue that
    wants a project delete owns.
    """

    __tablename__ = "shema_submissions"
    __table_args__ = (
        Index("ix_shema_submissions_project_received", "project_id", "received_at"),
        Index(
            "uq_shema_submissions_project_content",
            "project_id",
            "content_hash",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="RESTRICT"), nullable=False
    )
    #: The language name as the submission carried it, not as the project holds it today.
    language_name: Mapped[str] = mapped_column(String(200), default="", server_default="")
    submitted_by: Mapped[str] = mapped_column(String(200), default="", server_default="")
    received_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    #: The archived file, byte-identical to what arrived.
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    #: Content hash of the archived bytes — what makes a double import a no-op.
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)


class ShemaIntakeLink(Base):
    """A token that lets one team leader open one intake form, and nothing else.

    It is not a session and it mints no token pair. No console, no project data beyond the
    form, and it expires — three rules from ``docs/shema.md`` §6.6, of which only the expiry
    is a column, because the other two are about what the route serves.

    ``used_at`` records the first successful submission through the link and ``revoked_at``
    an explicit withdrawal. Both are timestamps rather than flags for the reason the sibling's
    ``retired_at`` records: *when* is the question a later reader asks and a boolean cannot
    answer. Neither is *the* guard — ``verify_intake_token`` composes expiry, revocation and
    the hash in one service function, so a future caller inherits all three.
    """

    __tablename__ = "shema_intake_links"
    __table_args__ = (Index("ix_shema_intake_links_project", "project_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    #: The raw token leaves once, at creation, and is never stored.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(UtcDateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(UtcDateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
