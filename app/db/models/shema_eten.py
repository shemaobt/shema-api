"""The ETEN credit ledger — the table whose filling rule is still open.

GATE-01 ([OBT-387]) holds the rule and ``docs/shema.md`` §9.1 says what is already known:
Karina Marinho answered the core on 14/aug/2026 — *a credit is one completed defined scope,
counted in* **approved** *chapters*, **not a divisor**, so a 25-chapter scope and a
260-chapter New Testament are worth one credit each. Formal confirmation is still owed, so
``accountFor`` stays one swappable pure function and this table stays the shape the contract
froze rather than the shape a rule would imply.

**A year with no data is not a year of zero credits, and nothing seeds this table.** The
export has ``inETEN`` false on all 127 records and no record has any progress history, so the
report renders empty — by honest accident, on a funder-facing screen. A backend that seeds
plausible rows to make it look populated is inventing numbers.

Two facts about the source data that land on this gate and are not this table's to fix: the
export's ``approvedUnits`` is a copy of ``translatedUnits`` on all 127 records, which is why
``shema_projects.approved_units_unverified`` exists for BE-16; and ``status`` records *that* a
project finished and never *when*, which is why ``shema_projects.completed_date`` exists.
Both are columns this issue gives so that closing the gate is not also a migration.
"""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import ETEN_CREDIT_SOURCE, ShemaEtenCreditSource
from app.db.types import UtcDateTime


class ShemaEtenCredit(Base):
    """One credit line: a project, a year, a count and where the count came from.

    **A stored ``manual`` entry overrides the computed value**, and ``calculated`` marks what
    the rule produced. That is why the unique key is ``(project_id, year, source)`` and not
    ``(project_id, year)``: both may legitimately exist for one year, and the read picks the
    manual one. A two-column key would make storing a computed value destroy the override
    that is supposed to beat it.

    ``credits`` is **nullable**, and the null is a third answer rather than a missing one: a
    project marked ``concluido`` whose history cannot date the completion earns *completed,
    year not recorded* — never a credit in whichever year happens to be on screen.

    ``Integer`` and not ``Numeric``: the gate's answer so far counts closed scopes, which are
    whole. If the confirmation returns a fractional rule, that is a column change BE-11 opens
    — a small, reversible one — where a ``Decimal`` chosen now to hedge would make every
    reader in the module carry a fractional type forever for a number that is not one.
    """

    __tablename__ = "shema_eten_credits"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "year", "source", name="uq_shema_eten_credits_project_year_source"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(
        String(120), ForeignKey("shema_projects.id", ondelete="CASCADE"), nullable=False
    )
    #: Read from the ISO date by field, never through a timezone-dependent conversion — it is
    #: what makes the ETEN year correct (FE-44 §7.8).
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    credits: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[ShemaEtenCreditSource] = mapped_column(ETEN_CREDIT_SOURCE, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
