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

    A table and not an enum because the list moves, and an enum member costs a migration
    to extend. GATE-01 (OBT-447, 26/aug/2026) confirmed exactly one name — *Shema
    Línguas* — and left the other four of PRD v1.1 §3 **undecided rather than retired**;
    the client also floated an editable area for funds, which is BE-10 (OBT-471). So the
    list is expected to grow, and a table is what lets it grow without a migration.

    ``provisional`` said *the gate has not confirmed this name*, and **the gate has since
    closed** — so the sentence no longer has a subject. What the flag can still mean is
    *nobody has confirmed this name yet*, which is why the default stays ``True``: the
    four names GATE-01 left undecided would be born marked, and a fund whose name nobody
    approved is not the same object as *Shema Línguas*. The one row the seed writes is
    confirmed and is written ``False``.

    **Nothing reads the flag**, and that is the part not to leave implicit: a column no
    query honours is a promise the database is not keeping. Giving it a reader or dropping
    it is BE-10's (OBT-471), which is also where the editable fund area lands — the two
    decisions are the same decision.

    **A fund is never deleted.** ``rr_fund_movements`` references it and the ledger is
    append-only, so a fund that stopped being one has to stay readable for the movements
    that already name it. Ready Vessels is the proof that this happens: GATE-01 ended it
    as a fund and no row survives here, but the day one ends *after* it has taken money,
    the answer is a flag and not a DELETE — also BE-10's, which is where the column and
    its reader belong together.

    No balance columns. *Alocado* and *comprometido* are sums over ``rr_fund_movements``
    and *disponível* is their difference — store two, derive the third (BE-07).
    **This must stay true, and GATE-01's D6 is where it would be lost:** the client asked
    for an editable *alocado* carrying who edited it and when, and the literal reading of
    that is ``allocated`` + ``updated_by`` + ``updated_at`` here. It is already built,
    and not as columns — an ``ALLOCATION`` movement carries ``created_by``,
    ``created_at`` and ``reason``, and a wrong one is corrected by a compensating
    movement. **No follow-up adds a balance column to this table.**
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
    from** (contract §6.2), and GATE-01 (OBT-447, 26/aug/2026) answered why that stays
    true: **the mesa assigns the fund at triage**, of the three shapes the gate offered,
    and no field enters the form — the 45 questions stay 45. So a request arrives with
    no fund and null is the legitimate state of one still in ``triagem``, never a gap.

    The invariant that comes with the answer is **a request does not enter ``aprovado``
    with ``fund_id IS NULL``** — a service rule for BE-08 (OBT-457) and deliberately
    **not** a DDL CHECK, because the same null is correct one column earlier. BE-11
    (OBT-470) owns it.

    ``created_by`` was nullable for GATE-02, whose variant 2 had no stable principal
    behind a team. **D1 answered accounts** (OBT-448, 27/aug/2026) — ``auto_approve`` is
    true and every person who fills the form is authenticated — so the variant that needed
    the null is not being built and the column is ``NOT NULL``. Pre-drawing the variant is
    what made this a nullability change rather than a redesign, which was the whole point
    of drawing it.

    The FK stops cascading to ``NULL`` in the same move, because it cannot: ``ON DELETE
    SET NULL`` against a ``NOT NULL`` column is a delete that fails at the wrong moment
    with the wrong message. It restricts instead, which is what ``rr_fund_movements``
    already does and for the same reason — **D7 answered that edits are audited always**,
    and a trail is written about an owner. Deleting a person who authored a request now
    fails as a foreign-key violation naming the row that holds on; what to do with that
    person — anonymise, deactivate, keep — is BE-15's (OBT-475) and is not a default to
    pick in a column definition.
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
    created_by: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
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
    from the payload. Both stay nullable because a wave-1 draft carries a typed name and
    no principal.

    **The uniqueness is now one evaluation per snapshot**, and GATE-02's D5 is what
    tightened it: *"a mesa quem decide"* (OBT-448, 27/aug/2026). The looser
    ``(snapshot_id, evaluator_id)`` was the floor both candidate answers shared, held on
    purpose while the gate was open — because tightening a constraint on an empty table is
    one line and loosening one after the mesa has used it costs data. The table is still
    empty; the line was spent.

    What the tightening removes is real and worth naming: two NULLs are never equal in
    SQL, so the old constraint allowed a snapshot any number of unauthored evaluations —
    every row the seed writes. It now allows exactly one, which is what the answer says,
    and the seed writes exactly one.

    ``evaluator_id`` does not stop mattering by leaving the key. D5 answered the question
    behind it separately: the person **signs on behalf of the mesa**, so the evaluation is
    the mesa's and the signature is a person's. Who was in the room when it was decided is
    a different fact and a different table — ``rr_evaluation_attendees``.

    ``team_note`` is the mesa's message **to the team** (client, 28/aug/2026: *"caso tenha
    a necessidade de revisão a equipe recebe um aviso"*) — the one field of this aggregate
    a team is allowed to read, served through the status projection and never through the
    evaluation itself. It lives here and not on the request because the mesa writes it in
    Parte C, under ``edit_evaluation``; nullable because *no note* and *an empty note* are
    different facts, the same reason a score is nullable. Added by ``20260830_rr03``
    (BE-06, OBT-455).
    """

    __tablename__ = "rr_evaluations"
    __table_args__ = (UniqueConstraint("snapshot_id", name="uq_rr_evaluations_snapshot"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    snapshot_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_snapshots.id", ondelete="CASCADE"), index=True
    )
    evaluator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[RRDecision | None] = mapped_column(_DECISION, nullable=True)
    comments: Mapped[str] = mapped_column(Text, default="", server_default="")
    team_note: Mapped[str | None] = mapped_column(Text, nullable=True)
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


class RREvaluationAttendee(Base):
    """One mesa member present when a decision was taken — minutes, not audit.

    GATE-02's D5 asked for two things the question had not offered: *"uma tag ou
    assinatura de qual dos membros da mesa estava representando a mesa"*, which is
    ``RREvaluation.evaluator_id``, and *"registro de quem eram as pessoas da mesa
    presentes na tomada de decisão"*, which is this. They are not the same record and
    neither derives from the other — confusing them builds a table that answers the wrong
    question.

    **It is an ata and not a trail**, which is why it carries no timestamp and no
    append-only trigger: it states who was in the room, and a room list written down wrong
    is corrected rather than compensated. The field-by-field trail of who changed what is
    ``RREvaluationFieldHistory``, and that one is append-only.

    BE-02 gives it a shape and **BE-06 fills it**. A member with no account cannot be
    recorded, because ``user_id`` is a real FK and not a typed name — which is the right
    refusal rather than a gap, and it is the second half of D1 that closes it: how the
    three privileged roles get their accounts is BE-17 (OBT-477).
    """

    __tablename__ = "rr_evaluation_attendees"

    evaluation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_evaluations.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)


class RRFundMovement(Base):
    """One entry of the append-only ledger.

    Every movement carries a fund — the FK is ``NOT NULL`` — because a balance is a sum
    over this table grouped by fund, and a movement without one is money that left no
    trace anywhere.

    Un-approving writes a **compensating movement** pointing at what it reverses through
    ``reverses_id``; it never updates or deletes, and the trigger on this table is what
    stops a service from being able to.

    ``request_id`` is nullable: an allocation puts money in a fund and answers to no
    request. ``created_by`` **is not**, and it stopped being for the reason
    ``rr_requests.created_by`` did — plus one this table has of its own. GATE-01's D6
    (OBT-447) put the authorship of an allocation *in the movement*: the Gestores enter
    *alocado*, and who did it and when is this row's ``created_by``/``created_at``, which
    is exactly why ``rr_funds`` gains no ``allocated``, ``updated_by`` or ``updated_at``.
    A movement with no author would empty that design of the thing it was chosen for.

    The seed used to be the second reason the column was nullable. That was a property of
    the seed, not of the ledger, and the seed now names an author (``seed_resource_requests``
    takes one and refuses to run without it) rather than the schema bending to accommodate
    a fixture.

    It is the one user FK in this module that does **not** cascade to ``NULL``, and the
    trigger above is why. ``ON DELETE SET NULL`` is an UPDATE on this table, so deleting a
    person who moved money raised ``rr_fund_movements is append-only`` from inside
    ``delete_user`` — measured, and the message named the wrong thing entirely. Leaving the
    reference to restrict is the answer the ledger already implies: an entry names who made
    it, and forgetting that is precisely what append-only forbids. The delete still fails,
    now as a foreign-key violation that says which row is holding on; what to do with a
    person who moved money — anonymise, deactivate, keep — is BE-15's (OBT-475), which is
    where D7's *"sim, sempre"* becomes behaviour, and it is not a default to pick here.
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
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class _RRFieldHistory:
    """The columns both trails share, and the reasoning behind each one.

    GATE-02's D7 answered *"sim, sempre mantenha os históricos das mudanças"* (OBT-448,
    27/aug/2026) over **both** the solicitação and the avaliação, field by field. The
    feature is BE-15's (OBT-475); **the tables are BE-02's**, and the reason is written in
    the design's own §10 — a history table is cheap before there is data and expensive
    after. Adding them here costs two ``create_table`` calls in a migration nobody has
    run; adding them later costs a second migration plus the admission that everything
    edited in between was not recorded.

    ``field_key`` is a string and not a column name, because a request's fields live in
    three places: six promoted columns on the spine, the 45 answers inside
    ``rr_request_sections.content``, and the 26 rows of ``rr_budget_lines``. One key space
    reaches all three; a design keyed on ``information_schema`` reaches only the first.

    ``old_value`` and ``new_value`` are nullable text, and the nulls are not a shortcut:
    D7's own example is *"quem subiu uma nota de 2 para 5"*, so both sides are needed, and
    a field that had no value before has no old side. Text rather than a typed column
    because the three homes hold strings, decimals, dates and integers, and a trail that
    can only record some of them is not a trail.

    ``changed_by`` is ``NOT NULL`` and restricts on delete, the same rule the ledger
    keeps: a record of who changed something is worth nothing if the who can be forgotten.
    It is the same answer D1 made possible — the document has an owner, and this is
    written about that owner.

    **Append-only, by the same trigger the ledger uses.** A history whose rows can be
    edited answers nothing, and it is one line in ``APPEND_ONLY_TABLES`` rather than a
    service rule that the second caller will not have.
    """

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    field_key: Mapped[str] = mapped_column(String(128))
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RRRequestFieldHistory(_RRFieldHistory, Base):
    """Who changed which field of a solicitação, from what to what, and when.

    It follows the request and not the snapshot, because the thing being audited is the
    editing — a snapshot is by definition the version that stopped moving.
    """

    __tablename__ = "rr_request_field_history"
    __table_args__ = (
        Index("ix_rr_request_field_history_request_changed", "request_id", "changed_at"),
    )

    request_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_requests.id", ondelete="CASCADE"), index=True
    )


class RREvaluationFieldHistory(_RRFieldHistory, Base):
    """Who changed which field of an avaliação, from what to what, and when.

    ``field_key`` here is a criterion key for a score, or ``decision`` / ``comments`` for
    the two fields that are not scores. The criterion keys are the same eighteen the
    vendored vocabularies carry, so a trail row and a score row name the criterion the
    same way and no translation sits between them.
    """

    __tablename__ = "rr_evaluation_field_history"
    __table_args__ = (
        Index("ix_rr_evaluation_field_history_evaluation_changed", "evaluation_id", "changed_at"),
    )

    evaluation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("rr_evaluations.id", ondelete="CASCADE"), index=True
    )


class RRBoardTransition(Base):
    """A card's move between two columns of the board.

    ``movement_id`` is how a stage change and the ledger entry it caused are visible as
    one event; BE-08 writes both in a single transaction, and only a move onto
    ``aprovado`` — or off it — has a movement at all.

    ``evaluation_id`` is the column the design's §4.4 handed to BE-08 to add or refuse,
    and it is added (OBT-457): GATE-02 D6 insists a decision's move and a hand's drag are
    different events — a decision implies a column, a column never implies a decision —
    and without this column the two land in the trail indistinguishable whenever no money
    moved. A decision-driven transition names the evaluation that caused it; a manual
    move carries ``NULL``, which is exactly the asymmetry D6 describes. No ``ondelete``,
    like ``movement_id``: an evaluation that moved a card is not unwound by disappearing,
    and a delete that would orphan the trail fails naming the row that holds on.

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
    evaluation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("rr_evaluations.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


event.listen(RRFundMovement.__table__, "after_create", _guard_append_only)
event.listen(RRSnapshot.__table__, "after_create", _guard_append_only)
event.listen(RRRequestFieldHistory.__table__, "after_create", _guard_append_only)
event.listen(RREvaluationFieldHistory.__table__, "after_create", _guard_append_only)
