"""The Rhythm meeting log - and the table GATE-02 decided nobody builds.

``docs/shema.md`` §5.9 made ``shema_meeting_log`` unconditional and
``shema_meeting_definitions`` **conditional on GATE-02** ([OBT-388]), because the expensive
question that gate held was *whether the meeting set differs by region* - a data-model fork
rather than a detail. **It answered on 22/set/2026: the set is the same in the seven regions.**
So the definitions table never exists; the set stays in code (``app/utils/shema_meetings.py``,
and ``RITMO_MEETINGS`` on the console), and a log's ``scope_key`` is the region it was held in.

**The period is derived by the server from the date and the cadence, never taken from the
client** (BE-10). ``app/utils/shema_derivations.py``'s ``period_key`` reads it off the day's
calendar fields and never constructs an instant: the prototype's own period key did, read the
month back in local time, and filed the 1st of a month under the previous month - and 1 January
under the previous *year*. The console keeps its own ``periodKey`` in ``src/utils/cadence.ts``
to find the current period's entry and compares it to this column as text, so the two are
**two owners of one spelling that must agree**, which ``tests/test_shema/test_periods.py``
pins.

[OBT-388]: https://linear.app/shema-obt/issue/OBT-388
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
    appending a second. BE-10's write reads the key's row and creates or rewrites it inside a
    savepoint, and the constraint is what makes that safe when two coordinators interleave: the
    second insert conflicts instead of landing, and is retried as the replacement it is
    (``app/services/shema/log_meeting.py``).

    ``scope_key`` is text and not the ``RegionKey`` enum, because the vocabulary it holds is
    *a region or* ``global`` — eight values today, where the enum has seven. An enum of eight
    would be a second region vocabulary to keep in step with the first, and the day the set is
    scoped by region after all is exactly when a fixed set would cost a migration. Text
    costs nothing and the service validates against the one owner of the seven.

    ``meeting_id`` is text for the same reason one level up: the meetings live in code, as
    GATE-02 decided, and a foreign key cannot point at a constant.
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
    #: ``2026-05``, ``2026-B3``, ``2026-Q2``, ``2026-H1`` or ``2026``, derived by the server from
    #: the date and the meeting's cadence.
    period: Mapped[str] = mapped_column(String(10), nullable=False)
    meeting_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
