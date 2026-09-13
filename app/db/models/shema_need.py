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

**Being seen is not being worked on** (BE-08). The failure this aggregate exists to make
visible is a need raised and never acknowledged by anybody, and that state has to be
*findable in a query* rather than remembered — so acknowledgement is a stamp of its own
(:attr:`ShemaNeed.acknowledged_at` and the two columns beside it) and not a fifth member of
:class:`~app.db.models.shema_enums.ShemaNeedStatus`. The lifecycle the product speaks is
*raised, seen, being attended, attended*; the vocabulary FE-44 froze has four members and the
console renders exactly those four in a ``<select>``, so the second axis lives beside the
first instead of inside it.

**An amount without its currency is not a number, and this module never converts one**
(BE-08). ``estimated_amount`` is ``Numeric(14, 2)`` and ``estimated_currency`` is ISO-4217,
and a ``CHECK`` keeps them together in both directions — the sibling's decision
(``docs/resource_requests.md`` §7.2) taken here for its reason and for one more: these seven
regions do not share a currency, so a single stored number would be a number whose meaning
depends on a column somebody could forget to select. Nothing converts on write, there is no
base currency and no rate anywhere in this module, and nothing sums across currencies or
across categories — *categories are not commensurable* and neither are pesos and rupiah.
"""

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    text,
)
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
    here would be this schema deciding what a field team meant. **BE-08 kept it and put the
    money beside it** rather than parsing it: :attr:`estimated_amount` and
    :attr:`estimated_currency` are what a query, a report and a donor spreadsheet read, and
    the free text stays exactly as somebody typed it — *a caveat is data too*, and the field
    that says ``"about 5.000, more if the second village joins"`` still says it.

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
        #: The third of the three axes the DoD asks a need to be queryable by. Its own index
        #: rather than a column appended to one of the two above: a B-tree serves its leading
        #: column, and *the high-urgency needs of every region* is the question the ``attention``
        #: preset asks without naming a project or a category.
        Index("ix_shema_needs_urgency_status", "urgency", "status"),
        #: **The sweep of** ``list_unacknowledged_needs`` — the one query the DoD asks for. It
        #: leads on ``acknowledged_at`` because that is the column with two values in practice
        #: (a day, or NULL) and the sweep always fixes it to NULL, which is the narrowest
        #: leading predicate the three have.
        Index("ix_shema_needs_unacknowledged", "acknowledged_at", "status", "submitted_at"),
        #: **Neither half of an amount travels alone.** A number with no currency is a number
        #: whose meaning depends on who reads it, and a currency with no number is a column
        #: filled by a form that lost its value — both are refused here rather than in a
        #: validator, because the DoD's line is an invariant of the data and not of one write
        #: path. ``app/models/shema_need.py`` refuses the same pair earlier and with a better
        #: message; this is what holds for a seed, an import and a psql session.
        CheckConstraint(
            "(estimated_amount IS NULL) = (estimated_currency IS NULL)",
            name="ck_shema_needs_amount_carries_currency",
        ),
        #: ISO-4217 and not a symbol: several currencies share a glyph and ``$`` is the worst
        #: of them (``docs/resource_requests.md`` §7.2). ``upper`` and ``length`` rather than a
        #: regular expression, because ``~`` is PostgreSQL's and this constraint has to be
        #: readable by the SQLite the suite runs on — which is the only dialect where a test
        #: can watch the database refuse a value.
        CheckConstraint(
            "estimated_currency IS NULL OR ("
            "length(estimated_currency) = 3 AND estimated_currency = upper(estimated_currency)"
            ")",
            name="ck_shema_needs_currency_is_iso_4217",
        ),
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

    #: **The amount, exactly**, and ``Numeric`` rather than ``Float`` for the sibling's
    #: measured reason (``docs/resource_requests.md`` §7.2): summing ``0.10`` and ``0.20``
    #: gives ``Decimal('0.30')`` here and ``0.30000000000000004`` through a float. Nothing in
    #: this module sums needs — categories are not commensurable and neither are currencies —
    #: but the column a report is later built on is not the place to leave error to accumulate.
    estimated_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    #: The ISO-4217 code the amount is in. **Stored with the value, always**, and never
    #: converted: seven regions do not share a currency, a rate is a fact about a day rather
    #: than about a need, and converting on write would destroy the number somebody typed in
    #: exchange for a number nobody chose.
    estimated_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)

    #: Reaches the prayer wall through this and only this.
    prayer_shared: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    #: Marks a need celebrated rather than removing it from the wall.
    prayer_answered: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )

    #: **The day somebody said they had seen this**, and the whole of the second axis. NULL
    #: is *nobody has*, which is the state ``list_unacknowledged_needs`` sweeps for; it is
    #: nullable with no default and nothing backfills it, for the reason ``docs/shema.md``
    #: §7.4 gives about the other two absences in this module — a default here would report
    #: every unanswered need as answered, which is the exact failure the column exists for.
    acknowledged_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Who acknowledged it. ``SET NULL`` on a deleted account, because the accountability copy
    #: is the name beside it — the same split ``shema_projects.updated_by`` already makes.
    acknowledged_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: A snapshot that must not follow a rename: *who saw this, as they were called then*.
    acknowledged_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

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
