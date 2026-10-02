"""The slug each Shemá project was born under, and the opaque id it answers to now (OBT-552).

The 127 imported records kept the Notion export's slug as their primary key —
``<language>-<place>`` — and the id travels unredacted on every shape that leaves the server: the
card, the prayer wall, the export file, the ETEN report, the notification panel. For a project in
a sensitive country that put back, in the address, the place the redaction had just withheld
(``sa-di-of-high-egypt`` says Egypt). Revision ``20261001_shema552`` gives every such record an
opaque UUID, the id every record created since OBT-551 already takes.

This table is what makes that revision reversible, and it is read by nothing else: no route
resolves an old slug, because a redirect from a slug is the existence question OBT-551 closed.
The old ids stay here, in the database, where the place they name is already stored in the clear.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.types import UtcDateTime


class ShemaProjectRekey(Base):
    """One project's move from its export slug to its opaque id."""

    __tablename__ = "shema_project_rekeys"

    old_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    new_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    rekeyed_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )
