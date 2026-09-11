"""The Rhythm meeting log — and the table this issue deliberately does not create.

``docs/shema.md`` §5.9 makes ``shema_meeting_log`` unconditional and
``shema_meeting_definitions`` **conditional on GATE-02** ([OBT-388]), and the conditional
half is the decision worth reading. The expensive question that gate holds is *whether the
meeting set differs by region* — a data-model fork rather than a detail. Today the log's
``scope_key`` carries a region or ``global`` while the five definitions are global; a
per-region set means the definition itself is scoped, which changes the table **and** the
readiness computation that reads it. Building either shape now would freeze a schema around a
guess, which §9 forbids by name. So the definitions stay in code until the client answers,
and BE-10 gets the table when the answer tells it which table to get.

**The period is derived by the server from the date and the cadence, never taken from the
client.** ``src/utils/cadence.ts`` is the single owner and it never constructs a date from
text: the prototype's own period key did, read the month back in local time, and filed the
1st of a month under the previous month — and 1 January under the previous *year*.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaMeetingLogEntry(Base):
    """One meeting, logged once for one scope and one period.

    **Unique per** ``(meeting_id, scope_key, period)``, and the constraint is the behaviour:
    logging a meeting for a period that already has an entry **replaces** it rather than
    appending a second, so the upsert BE-10 writes has a key to conflict on instead of a
    read-then-write that two coordinators can interleave.

    ``scope_key`` is text and not the ``RegionKey`` enum, because the vocabulary it holds is
    *a region or* ``global`` — eight values today, where the enum has seven. An enum of eight
    would be a second region vocabulary to keep in step with the first, and GATE-02 may scope
    the definitions themselves, which is exactly when a fixed set costs a migration. Text
    costs nothing and the service validates against the one owner of the seven.

    ``meeting_id`` is text for the same reason one level up: the five meetings live in code
    until GATE-02 says whether they are a table, and a foreign key cannot point at a
    constant.
    """

    __tablename__ = "shema_meeting_log"
    __table_args__ = (
        UniqueConstraint(
            "meeting_id", "scope_key", "period", name="uq_shema_meeting_log_meeting_scope_period"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    meeting_id: Mapped[str] = mapped_column(String(60), nullable=False)
    #: A ``RegionKey`` or ``global``.
    scope_key: Mapped[str] = mapped_column(String(30), nullable=False)
    #: ``2026-05``, ``2026-Q2`` or ``2026``, derived by the server from the date and cadence.
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
