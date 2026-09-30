"""``shema_exports`` — one row per file the export route produced, BE-14's audit trail.

**An export is the moment data stops being governed by this system**, and the issue's reason for
logging it is the whole design: after the file leaves, *who exported what, when* is the one
question nobody can answer from anywhere else. So every ``GET /api/shema/export/projects`` that
answers writes a row here before the file is handed back, and the file names the row it belongs
to (``meta.exportId``, the CSV's provenance line), so a copy found later leads back to it.

**What is kept is the fact, never the content.** Who (the account and the name as it was then),
when, over which scope, in which format, how many projects and how many of them left with their
place withheld, and **which** projects and which prayer requests went out — by id. Not a word of
text: a request that is withdrawn later must not survive in the one table that cannot be edited,
and a place copied here would be out of reach of a flag raised afterwards (the boundary
``_audit.py`` keeps for the record's trail and ``shema_eten_reports`` for the report, for the same
reason). The ids answer *was my request in that file* without holding the request.

**Append-only in the database**, by the trigger ``shema_progress_history`` and
``shema_eten_reports`` already use: a log of what left that can be edited is a log of nothing.
``exported_by`` restricts for the same reason ``computed_by`` does there — a *who* that can be
deleted is not a record of anything.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, Index, Integer, String, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import guard_append_only
from app.db.types import UtcDateTime


class ShemaExport(Base):
    """One export as it was answered: who, when, what scope, what format, and what left."""

    __tablename__ = "shema_exports"
    __table_args__ = (Index("ix_shema_exports_created_at", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exported_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    #: The exporter's name **as it was then** — the name the file itself printed.
    exported_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: ``global``, or the caller's regions sorted and comma-joined — ``shema_eten_reports``'
    #: own spelling of a scope, so the two logs join on it.
    scope_key: Mapped[str] = mapped_column(String(200), nullable=False)
    #: ``json`` or ``csv``.
    format: Mapped[str] = mapped_column(String(8), nullable=False)
    project_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: How many rows left with their place withheld — counted whoever exported, because the log
    #: is read by somebody investigating, not by the exporter.
    withheld_count: Mapped[int] = mapped_column(Integer, nullable=False)
    #: The slugs of the projects in the file, in the file's order.
    project_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    #: The ids of the authorized prayer requests in the file (``_consent.AuthorizedRequest.id``).
    request_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    #: Stamped from Python as well, so the row and the file's ``generatedAt`` are one instant.
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


event.listen(ShemaExport.__table__, "after_create", guard_append_only)
