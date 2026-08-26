"""SQLAlchemy tables for the ``resource_requests`` module.

The four aggregates FE-22 froze — request document, evaluation, fund and ledger, board
move — plus the snapshot the first three hang from. ``docs/resource_requests.md`` is the
design this implements; where a decision was left to this issue, the class docstring
below carries it.

Money is ``Numeric(14, 2)`` mapped to ``Decimal`` and currency is ISO-4217, both decided
in the design's §7.2. The frontend persists the symbol (``R$``); translating it is
INT-02's client, not this schema's business.

Three columns that a reader will expect to carry ``index=True`` deliberately do not —
``rr_requests.stage``, ``rr_fund_movements.fund_id`` and ``rr_board_transitions.request_id``.
Each already leads a composite (`(stage, created_at)`, `(fund_id, created_at)`,
`(request_id, created_at)`), and a B-tree serves its leading column on its own, so a second
index would cost every write and buy no read.

Two tables are append-only and say so in the database rather than only in a service:
``rr_fund_movements`` and ``rr_snapshots``. ``append_only_ddl`` builds the guard for the
dialect in hand and is hung on ``after_create`` so ``Base.metadata.create_all`` — which
is how the test suite builds its schema — gets the same protection the migration writes.
"""

import enum
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.core.database import Base


class RRRequestType(enum.StrEnum):
    TRADUCAO = "traducao"
    TREINAMENTO = "treinamento"
    EQUIPAMENTOS = "equipamentos"


class RRStage(enum.StrEnum):
    TRIAGEM = "triagem"
    ANALISE = "analise"
    APROVADO = "aprovado"
    CONDICIONAL = "condicional"
    REVISAR = "revisar"
    RECUSADO = "recusado"


class RRDecision(enum.StrEnum):
    APPROVED = "approved"
    CONDITIONAL = "conditional"
    REVISE = "revise"
    DECLINED = "declined"


class RRCurrency(enum.StrEnum):
    BRL = "BRL"
    USD = "USD"
    EUR = "EUR"


class RRMovementKind(enum.StrEnum):
    ALLOCATION = "allocation"
    COMMITMENT = "commitment"
    APPROVAL_DEDUCTION = "approval_deduction"
    REVERSAL = "reversal"


def _enum_type(enum_cls: type[enum.StrEnum], name: str) -> Enum:
    """A native PostgreSQL enum that stores the member *values*, not their names.

    ``values_callable`` is not optional: without it the type is written from the member
    names, and the contract froze the lowercase values.

    ``create_constraint`` has defaulted to ``False`` since SQLAlchemy 1.4, which on a
    dialect without native enums leaves a bare ``VARCHAR`` — and the test suite runs on
    SQLite. Turning it on costs PostgreSQL nothing (a native enum is already a closed set
    and no CHECK is emitted beside it) and is what makes the four frozen decision strings
    refused by the database in the only place a test can see it happen.
    """
    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda cls: [m.value for m in cls],
        create_constraint=True,
    )


_REQUEST_TYPE = _enum_type(RRRequestType, "rr_request_type_enum")
_STAGE = _enum_type(RRStage, "rr_stage_enum")
_DECISION = _enum_type(RRDecision, "rr_decision_enum")
_CURRENCY = _enum_type(RRCurrency, "rr_currency_enum")
_MOVEMENT_KIND = _enum_type(RRMovementKind, "rr_movement_kind_enum")

APPEND_ONLY_FUNCTION = "rr_reject_write"


def append_only_ddl(table_name: str, dialect: str) -> tuple[str, ...]:
    """The statements that make ``table_name`` reject every UPDATE and DELETE.

    PostgreSQL needs a trigger function, shared by every append-only table here and
    written with ``CREATE OR REPLACE`` so a second table costs nothing. SQLite has no
    stored functions and raises from the trigger body instead, one trigger per verb.
    """
    if dialect == "postgresql":
        return (
            f"CREATE OR REPLACE FUNCTION {APPEND_ONLY_FUNCTION}() RETURNS trigger AS $$ "
            f"BEGIN RAISE EXCEPTION '% is append-only', TG_TABLE_NAME; END; $$ LANGUAGE plpgsql",
            f"CREATE TRIGGER {table_name}_append_only "
            f"BEFORE UPDATE OR DELETE ON {table_name} "
            f"FOR EACH ROW EXECUTE FUNCTION {APPEND_ONLY_FUNCTION}()",
        )
    message = f"{table_name} is append-only"
    return (
        f"CREATE TRIGGER {table_name}_no_update BEFORE UPDATE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
        f"CREATE TRIGGER {table_name}_no_delete BEFORE DELETE ON {table_name} "
        f"BEGIN SELECT RAISE(ABORT, '{message}'); END",
    )


def _guard_append_only(table: Table, connection: Connection, **_: Any) -> None:
    for statement in append_only_ddl(table.name, connection.dialect.name):
        connection.execute(text(statement))


class RRFund(Base):
    """One of the Resource Circle's funds.

    A table and not an enum because GATE-01 may still add, drop or rename one, and an
    enum member costs a migration to extend. ``provisional`` carries exactly that: the
    five rows the seed writes are the PRD's names laid over the prototype's ids, and the
    gate has not confirmed the correspondence.

    No balance columns. *Alocado* and *comprometido* are sums over ``rr_fund_movements``
    and *disponível* is their difference — store two, derive the third (BE-07).
    """

    __tablename__ = "rr_funds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    provisional: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RRRequest(Base):
    """The queried spine of a request document.

    The columns here are the ones the board, the lists and the cycle indicators read;
    everything else the form asks lives in ``rr_request_sections`` and
    ``rr_budget_lines``. Six of the contract's 45 text keys are promoted to columns —
    ``reg_name``, ``amount_requested``, ``tpp_name``, ``tpp_date``, ``leader_name``,
    ``leader_date`` — and they must not also appear among the section answers: a value
    with two homes is a value with no owner.

    ``amount_requested`` is item 9, typed by hand and never the budget total. It is what
    the board card shows as *valor* and what a fund commits on approval, which is why it
    is a column and the budget total is not one at all — a derived number is recomputed
    (BE-05), never stored.

    ``fund_id`` is nullable because **nothing in the form says which fund a request asks
    from** (contract §6.2). Whether the team chooses, the type decides or the mesa
    assigns at triage is Open · GATE-01; the column is where the answer lands in all
    three shapes, so it exists, empty.

    ``created_by`` is nullable for GATE-02: variant 2 of the design's §5 has no stable
    principal behind a team, and a FK that cannot be satisfied would be the one thing the
    gate could force a redesign of.
    """

    __tablename__ = "rr_requests"
    __table_args__ = (Index("ix_rr_requests_stage_created", "stage", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_type: Mapped[RRRequestType] = mapped_column(_REQUEST_TYPE)
    reg_name: Mapped[str] = mapped_column(String(255), default="", server_default="")
    stage: Mapped[RRStage] = mapped_column(_STAGE, default=RRStage.TRIAGEM)
    currency: Mapped[RRCurrency] = mapped_column(_CURRENCY, default=RRCurrency.BRL)
    fund_id: Mapped[str | None] = mapped_column(
        String(32), ForeignKey("rr_funds.id"), nullable=True, index=True
    )
    amount_requested: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    declaration: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    tpp_name: Mapped[str] = mapped_column(String(160), default="", server_default="")
    tpp_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    leader_name: Mapped[str] = mapped_column(String(160), default="", server_default="")
    leader_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    revision_of_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("rr_snapshots.id", use_alter=True, name="fk_rr_requests_revision_of"),
        nullable=True,
    )
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RRRequestSections(Base):
    """Everything Parte A and Parte B ask that is not spine and not a budget line.

    The design's §4.2 left the medium to this issue: rows keyed by field, or one
    document. It is a document, for two reasons that agree. The sections are read whole
    by exactly one screen and nothing in the product queries a single answer — the same
    asymmetry that made the spine columns in the first place, applied one level down.
    And submission freezes a snapshot of this same shape (``rr_snapshots.document``), so
    the freeze is a copy rather than a projection, and BE-04 has no second serializer to
    keep in step with the read path.

    Its own table rather than a column on ``rr_requests`` so the board and the lists
    never drag the document they do not read.

    ``content`` mirrors the contract's ``RequestDraft`` minus the promoted spine keys,
    minus ``budget`` (rows, ``rr_budget_lines``) and minus the evaluation (its own
    aggregate, §2 of the contract)::

        {"fields": {...}, "langs": [...], "team": [...], "chrono": [...],
         "checks": {"teamtype": [...], "trainformat": [...]}}

    A key **absent** from ``fields`` was never asked, an empty string was asked and not
    answered. The mesa reads that difference, so nothing may fill the document out.
    """

    __tablename__ = "rr_request_sections"

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_requests.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")


class RRBudgetLine(Base):
    """One of the 26 fixed budget categories, as a row.

    Keyed by ``category_key`` and never by position: reordering the frontend's list would
    silently rewrite every stored row if the index were the key (design §4.3). The 26
    slugs themselves arrive with the vendored vocabulary emission the design's §9 names;
    membership is BE-05's check, which is why this column is a string and not an enum —
    the list is the client's to extend.

    ``quantity`` is ``Numeric`` and not money: the *Qtd. de itens* column never
    multiplies anything (it is the export's arithmetic, and the contract keeps it), so
    it is stored as the number it is and used by nothing.

    Cardinality is not enforced here. A draft is filled over days and a table that
    refuses 25 rows refuses the way the form is actually used; "all 26 present" is a
    submission rule and belongs to BE-05.
    """

    __tablename__ = "rr_budget_lines"

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_requests.id", ondelete="CASCADE"), primary_key=True
    )
    category_key: Mapped[str] = mapped_column(String(48), primary_key=True)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)


class RRSnapshot(Base):
    """The frozen document a submission produced, and what an evaluation points at.

    Append-only in the database. What the mesa scored has to stay exactly as scored, and
    a revision is a *new* request row carrying ``revision_of_id`` back to this one — so
    nothing ever needs to rewrite a snapshot, and the trigger makes "never" a fact rather
    than a convention.

    ``document`` carries the whole request as submitted: the spine values, the sections
    document and the budget lines. Deliberately self-contained — a snapshot that had to
    join live tables to be read would not be frozen.
    """

    __tablename__ = "rr_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), ForeignKey("rr_requests.id"), index=True)
    document: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RREvaluation(Base):
    """The mesa's evaluation — its own aggregate, hanging off a snapshot.

    It is not nested in the request document, and that is the one shape from wave 1 not
    to copy: Parte C is gated by ``view_evaluation``, so an evaluation carried inside a
    request response would hand a team the scores the screen refuses it.

    The ``/30`` total is not a column. It is the sum of ``rr_evaluation_scores`` and is
    recomputed on every read (BE-05), like every other derived number here.

    ``evaluator_id`` and ``evaluated_at`` are stamped from the session by BE-06, never
    from the payload. Both are nullable because a wave-1 draft carries a typed name and
    no principal, and because the unique constraint below has to hold before GATE-02
    answers: **one evaluation per snapshot per evaluator** is the floor both candidate
    answers share — "one per mesa" is the same constraint tightened, and tightening a
    constraint later costs a migration, where loosening one costs data.

    That floor reaches exactly as far as the evaluator is known, and no further: two NULLs
    are never equal in SQL, so a snapshot may carry any number of evaluations with no
    principal — which is every row the seed writes. It is the right shape rather than a
    hole, because the day an evaluation is authored at all is the day BE-06 stamps the
    session onto it; until then there is no evaluator for a uniqueness rule to be about.
    """

    __tablename__ = "rr_evaluations"
    __table_args__ = (
        UniqueConstraint(
            "snapshot_id", "evaluator_id", name="uq_rr_evaluations_snapshot_evaluator"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_snapshots.id", ondelete="CASCADE"), index=True
    )
    evaluator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[RRDecision | None] = mapped_column(_DECISION, nullable=True)
    comments: Mapped[str] = mapped_column(Text, default="", server_default="")
    evaluated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class RREvaluationScore(Base):
    """One criterion's score, 0-5, keyed by the criterion and never by position.

    ``score`` is nullable because *not scored* and *scored zero* are different answers,
    and the contract separates them in the type for exactly that reason. The range is a
    CHECK rather than a service rule: the frontend already clamps, and a clamp that only
    exists in the client is a clamp a second client will not have.
    """

    __tablename__ = "rr_evaluation_scores"
    __table_args__ = (
        CheckConstraint(
            "score IS NULL OR (score >= 0 AND score <= 5)", name="ck_rr_evaluation_scores_range"
        ),
    )

    evaluation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_evaluations.id", ondelete="CASCADE"), primary_key=True
    )
    criterion_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)


class RRFundMovement(Base):
    """One entry of the append-only ledger.

    Every movement carries a fund — the FK is ``NOT NULL`` — because a balance is a sum
    over this table grouped by fund, and a movement without one is money that left no
    trace anywhere.

    Un-approving writes a **compensating movement** pointing at what it reverses through
    ``reverses_id``; it never updates or deletes, and the trigger on this table is what
    stops a service from being able to.

    ``request_id`` is nullable: an allocation puts money in a fund and answers to no
    request. ``created_by`` is nullable for the same reason ``rr_requests.created_by``
    is, and because the seed's sample allocations have no author.

    It is the one user FK in this module that does **not** cascade to ``NULL``, and the
    trigger above is why. ``ON DELETE SET NULL`` is an UPDATE on this table, so deleting a
    person who moved money raised ``rr_fund_movements is append-only`` from inside
    ``delete_user`` — measured, and the message named the wrong thing entirely. Leaving the
    reference to restrict is the answer the ledger already implies: an entry names who made
    it, and forgetting that is precisely what append-only forbids. The delete still fails,
    now as a foreign-key violation that says which row is holding on; what to do with a
    person who moved money — anonymise, deactivate, keep — is the audit-trail question
    §10 already carries under GATE-02, and it is not a default to pick here.
    """

    __tablename__ = "rr_fund_movements"
    __table_args__ = (Index("ix_rr_fund_movements_fund_created", "fund_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    fund_id: Mapped[str] = mapped_column(String(32), ForeignKey("rr_funds.id"))
    request_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rr_requests.id"), nullable=True, index=True
    )
    kind: Mapped[RRMovementKind] = mapped_column(_MOVEMENT_KIND)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[RRCurrency] = mapped_column(_CURRENCY, default=RRCurrency.BRL)
    reverses_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rr_fund_movements.id"), nullable=True
    )
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    created_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RRBoardTransition(Base):
    """A card's move between two columns of the board.

    ``movement_id`` is how a stage change and the ledger entry it caused are visible as
    one event; BE-08 writes both in a single transaction, and only a move onto
    ``aprovado`` — or off it — has a movement at all.

    ``from_stage`` is nullable for the first row of a request's history, where there is
    no column it came from.
    """

    __tablename__ = "rr_board_transitions"
    __table_args__ = (Index("ix_rr_board_transitions_request_created", "request_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_requests.id", ondelete="CASCADE")
    )
    from_stage: Mapped[RRStage | None] = mapped_column(_STAGE, nullable=True)
    to_stage: Mapped[RRStage] = mapped_column(_STAGE)
    moved_by: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    movement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rr_fund_movements.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


event.listen(RRFundMovement.__table__, "after_create", _guard_append_only)
event.listen(RRSnapshot.__table__, "after_create", _guard_append_only)
