"""Needs and resources — the items that travel with the project.

``docs/shema.md`` §5.4: needs are edited on the record's tabs and saved by the record's
``PATCH``. There is **no separate needs endpoint in wave 1**, and adding one would give
``needsItems`` a second owner. This is a table rather than a JSON column on the record all
the same, because a need is the one sub-shape the product queries across projects — the
*attention* preset reads open high-urgency needs, the prayer wall reads ``prayer_shared``,
and the celebrate preset reads ``prayer_answered``.

**Four states, not three.** ``dropped`` is what lets a request that stopped mattering leave
the open list without being deleted, because deleting loses the history a region is judged
by. *Still outstanding* is ``open`` or ``in-progress``, and it has one owner.

**Urgency is not health.** The two never share a vocabulary and the health derivation never
reads a need.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import (
    NEED_STATUS,
    NEED_URGENCY,
    ShemaNeedStatus,
    ShemaNeedUrgency,
)
from app.db.types import UtcDateTime


class ShemaNeed(Base):
    """One need raised against one project.

    **The ``id`` is the row's, and whether it becomes the contract's is BE-08's.**
    ``NeedItem`` carries no id today: a derived notification identifies one by
    ``(project, category, submittedAt)``, and ``docs/shema.md`` §10's item 6 hands the
    question of a server-side id to BE-08 because it changes the shape the client sees. A
    table needs a primary key whatever that answer is, so this is one and it means nothing
    about the contract; giving the row a uuid does not decide to publish it.

    ``category`` is text and not an enum, which is the one place this module departs from
    its own sibling fields. §7.3's enum-safe list carries ``NeedUrgency`` and ``NeedStatus``
    and leaves ``NeedCategory`` out — the test there is whether the client can extend the
    list, and a category list is exactly the kind that grows. It is indexed because the
    *categoria de necessidade* facet asks the join from this side.

    ``estimated_value`` is a string because the contract types it as one: the field records
    an amount as it was typed, with its currency and its caveats, and parsing it into money
    here would be this schema deciding what a field team meant.

    ``submitted_at`` is a ``Date`` and not a moment. It is half of the identity a derived
    notification is keyed by (``need:{project}:{category}:{submittedAt}``), and FE-44 §5.8's
    stable-id rule is what makes the read state in ``shema_notification_reads`` safe — so
    its stored form has to be the one the id is built from. A day is what the product shows
    and what every other date in this module stores; a timestamp would put a UTC instant
    inside an id the coordinator reads.
    """

    __tablename__ = "shema_needs"
    __table_args__ = (
        Index("ix_shema_needs_project_status", "project_id", "status"),
        Index("ix_shema_needs_category_status", "category", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )

    category: Mapped[str] = mapped_column(String(60), nullable=False)
    urgency: Mapped[ShemaNeedUrgency] = mapped_column(NEED_URGENCY, nullable=False)
    status: Mapped[ShemaNeedStatus] = mapped_column(
        NEED_STATUS, default=ShemaNeedStatus.OPEN, server_default=text("'open'")
    )
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    estimated_value: Mapped[str | None] = mapped_column(String(120), nullable=True)
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Reaches the prayer wall through this and only this.
    prayer_shared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    #: Marks a need celebrated rather than removing it from the wall.
    prayer_answered: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    fulfilled_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fulfilled_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    dropped_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(200), nullable=True)
    submitted_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
