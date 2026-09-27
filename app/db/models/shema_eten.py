"""The ETEN ledger and the reports the server answered — BE-11's two tables.

GATE-01 closed on 25/sep/2026 (OBT-387) and the rule lives in
``app/utils/shema_derivations.py``'s ``account_for``: a credit is one completed defined scope,
counted in **approved** chapters, never a divisor, in ETEN's fiscal year (August to July).

**A year with no data is not a year of zero credits, and nothing seeds either table.** The
export has ``inETEN`` false on all 127 records and no record has any progress history, so the
report renders empty — by honest accident, on a funder-facing screen. A backend that seeds
plausible rows to make it look populated is inventing numbers.

Two facts about the source data land on this module and are other columns' to carry: the
export's ``approvedUnits`` is a copy of ``translatedUnits`` on all 127 records, which is why
``shema_projects.approved_units_unverified`` exists and why the rule reads it; and ``status``
records *that* a project finished and never *when*, which is why ``shema_projects.completed_date``
exists and why ``save_project`` now stamps it.
"""

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import JSON, Date, ForeignKey, Index, Integer, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base
from app.db.models.shema_enums import ETEN_CREDIT_SOURCE, ShemaEtenCreditSource, guard_append_only
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

    ``Integer`` and not ``Numeric``: the confirmed rule counts closed scopes, which are whole.

    **BE-11 stores only** ``manual`` **rows here.** A calculated credit written into this table
    would be a figure without the data that produced it, which is the one thing the issue asks
    the report never to be; the calculated figure is kept in :class:`ShemaEtenReport`, beside
    its readings. It also keeps ``GET /api/shema/eten/credits`` what the console already reads
    it as — ``accountFor`` treats every ledger row it is handed as the override.

    **A manual row names who set it**, because an override of a funder-facing number is the row
    somebody will be asked about. It is overwritten by the next ``PUT`` for the same project and
    year; the value a report used before that is kept by the report.
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
    #: The account that set a manual figure. ``SET NULL`` because this row is mutable and the
    #: name beside it is what the report reads; the name is the accountability snapshot.
    recorded_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    #: The setter's name **as it was then** — a rename does not change who set the figure.
    recorded_by_name: Mapped[str] = mapped_column(String(200), default="", server_default="")

    updated_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ShemaEtenReport(Base):
    """One ETEN report as the server answered it, with the data it was computed from.

    The issue's sentence is the design: *a report run in March and re-run in June will differ
    as data changes, and both may be correct — but only if it is recorded which data produced
    which figure.* So every ``GET /api/shema/eten/report`` is recorded here, **deduplicated**
    against the newest row for the same year and scope by a digest of its content: reopening an
    unchanged report writes nothing, and a report whose figures moved is a new row while the old
    one keeps saying what it said. The July report sent to ETEN is therefore on record whether
    or not anybody thought to save it.

    **The content holds no place name.** Each row carries the project, its language, its
    **region** and whether its place was withheld, plus every number and the evidence behind it
    — the history entries read, the completion date, the manual entry and who set it. It does
    **not** carry the country a row that was not flagged showed: a country copied into an
    append-only table is out of reach of a flag raised later, which is the boundary
    ``_audit.py`` keeps for the trail and for the same reason. The country is not an input of the
    credit, so nothing the figure was computed from is lost.

    **Append-only in the database** (the trigger ``shema_progress_history`` uses): a record of
    what was reported that can be edited records nothing. ``computed_by`` restricts for the
    trail's reason — a *who* that can be deleted is not a record of anything.

    No unique key on the digest: a report that went A, then B, then A again is three answers and
    the third is not the first. Two simultaneous reads of a report that just changed can record
    the same content twice, which is a true double record rather than a wrong one.
    """

    __tablename__ = "shema_eten_reports"
    __table_args__ = (
        Index("ix_shema_eten_reports_year_scope_created", "year", "scope_key", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    #: The fiscal year, as ``?year=`` names it: the one that ends on 31 July of this year.
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Whose view this is: ``global``, or the caller's regions sorted and comma-joined. A
    #: report is scoped like every read in the module, so two scopes are two reports.
    scope_key: Mapped[str] = mapped_column(String(200), nullable=False)
    #: The day the report was first computed for. Decides only which year was still open.
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    #: sha256 of the canonical JSON of :attr:`content`, what deduplication compares.
    digest: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    computed_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    computed_by_name: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Stamped from Python as well: two reports recorded inside one transaction's clock would
    #: otherwise tie, and "the newest" is what deduplication asks for.
    created_at: Mapped[datetime] = mapped_column(
        UtcDateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(UTC),
    )


event.listen(ShemaEtenReport.__table__, "after_create", guard_append_only)
