"""The four constraints BE-02 owes the database, each proved by violating it.

They are in the schema and not only in a service because a rule that lives in one caller
is a rule the second caller will not have. Every test here writes through the connection
rather than through the ORM where the ORM would refuse first: SQLAlchemy's ``Enum``
rejects an unknown member in Python, and a test that stopped there would prove nothing
about the database.

These run on SQLite, which is what the suite has. The two dialects enforce the same four
rules by different means — a CHECK where PostgreSQL has a native enum, a pair of
``RAISE(ABORT)`` triggers where it has one plpgsql trigger — and
``app.db.models.resource_request.append_only_ddl`` is where that split lives.
"""

import importlib.util
from contextlib import asynccontextmanager
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DatabaseError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

import scripts.seed_resource_requests as seed_script
from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationAttendee,
    RREvaluationFieldHistory,
    RREvaluationScore,
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRRequestFieldHistory,
    RRSnapshot,
    RRStage,
    append_only_ddl,
)
from app.services.resource_request import fund_balances
from scripts.seed_resource_requests import SEED_CARDS, _spread
from tests.baker import make_user

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260825_rr01_resource_request_module.py"
)


@pytest.fixture()
async def author(db_session: AsyncSession):
    """The account every row that names an author is written by.

    ``created_by`` stopped being nullable when GATE-02's D1 answered accounts, so a
    fixture that used to be three lines of data now needs a person — which is the whole
    change stated in the smallest place it shows.
    """
    return await make_user(db_session, email="autor@fixture.test")


@pytest.fixture()
async def fund(db_session: AsyncSession) -> RRFund:
    row = RRFund(id="linguas", name="Shema Línguas")
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def movement(db_session: AsyncSession, fund: RRFund, author) -> RRFundMovement:
    row = RRFundMovement(
        id="m1",
        fund_id=fund.id,
        kind=RRMovementKind.ALLOCATION,
        amount=Decimal("480000"),
        created_by=author.id,
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def evaluation(db_session: AsyncSession, author) -> RREvaluation:
    """Flushed one table at a time, because request and snapshot reference each other.

    ``rr_requests.revision_of_id`` points at a snapshot and ``rr_snapshots.request_id``
    points back, and no ``relationship()`` tells the unit of work which way to break the
    tie — so a single flush is free to write the evaluation before its snapshot exists.
    """
    db_session.add(
        RRRequest(
            id="r1",
            request_type="traducao",
            stage="triagem",
            currency="BRL",
            created_by=author.id,
        )
    )
    await db_session.flush()
    db_session.add(RRSnapshot(id="s1", request_id="r1"))
    await db_session.flush()

    row = RREvaluation(id="e1", snapshot_id="s1")
    db_session.add(row)
    await db_session.commit()
    return row


async def test_a_score_above_five_is_refused(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    db_session.add(
        RREvaluationScore(evaluation_id=evaluation.id, criterion_key="traducao_orcamento", score=6)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_a_negative_score_is_refused(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    db_session.add(
        RREvaluationScore(evaluation_id=evaluation.id, criterion_key="traducao_orcamento", score=-1)
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_an_unscored_criterion_is_not_a_zero(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    """The range check must not turn *not scored* into a violation, or into a 0/30."""
    db_session.add(
        RREvaluationScore(
            evaluation_id=evaluation.id, criterion_key="traducao_orcamento", score=None
        )
    )
    await db_session.commit()

    stored = await db_session.get(RREvaluationScore, (evaluation.id, "traducao_orcamento"))
    assert stored is not None
    assert stored.score is None


async def test_a_decision_outside_the_four_is_refused(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    """Written as SQL: the ORM's Enum would refuse ``rejected`` before the database saw it."""
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text("UPDATE rr_evaluations SET decision = 'rejected' WHERE id = :id"),
            {"id": evaluation.id},
        )
        await db_session.commit()


async def test_each_of_the_four_decisions_is_accepted(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    """The four literals are FE-22's contract, not ``RRDecision`` read back to itself.

    Iterating the enum would ask the constraint whether it agrees with the thing that
    generated it, which it cannot fail. Typed out, this is the other direction of the
    test above: the check refuses a fifth string and admits exactly these four.
    """
    for decision in ("approved", "conditional", "revise", "declined"):
        await db_session.execute(
            text("UPDATE rr_evaluations SET decision = :decision WHERE id = :id"),
            {"decision": decision, "id": evaluation.id},
        )
    await db_session.commit()


async def test_a_movement_cannot_be_updated(
    db_session: AsyncSession, movement: RRFundMovement
) -> None:
    with pytest.raises(DatabaseError, match="append-only"):
        await db_session.execute(
            text("UPDATE rr_fund_movements SET amount = 1 WHERE id = :id"), {"id": movement.id}
        )


async def test_a_movement_cannot_be_deleted(
    db_session: AsyncSession, movement: RRFundMovement
) -> None:
    with pytest.raises(DatabaseError, match="append-only"):
        await db_session.execute(
            text("DELETE FROM rr_fund_movements WHERE id = :id"), {"id": movement.id}
        )


async def test_a_snapshot_cannot_be_rewritten(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    """What the mesa scored stays exactly as scored, and the database is what says so."""
    with pytest.raises(DatabaseError, match="append-only"):
        await db_session.execute(text("UPDATE rr_snapshots SET document = '{}' WHERE id = 's1'"))


async def test_a_movement_without_a_fund_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO rr_fund_movements (id, kind, amount, currency, reason, created_at) "
                "VALUES ('m2', 'allocation', 1, 'BRL', '', CURRENT_TIMESTAMP)"
            )
        )
        await db_session.commit()


async def test_deleting_the_person_who_moved_money_is_refused(
    db_session: AsyncSession, fund: RRFund
) -> None:
    """The ledger names who made an entry, and the reference restricts rather than nulls.

    ``ON DELETE SET NULL`` here would be an UPDATE on an append-only table, so the delete
    used to raise ``rr_fund_movements is append-only`` from inside ``delete_user`` — a
    true sentence about the wrong thing. It now fails as what it is: a row still points
    at that person.
    """
    mover = await make_user(db_session, email="quem@moveu.test")
    db_session.add(
        RRFundMovement(
            id="m4",
            fund_id=fund.id,
            kind=RRMovementKind.ALLOCATION,
            amount=Decimal("10"),
            created_by=mover.id,
        )
    )
    await db_session.commit()

    await db_session.delete(mover)
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_a_movement_against_an_unknown_fund_is_refused(
    db_session: AsyncSession, author
) -> None:
    db_session.add(
        RRFundMovement(
            id="m3",
            fund_id="nao-existe",
            kind=RRMovementKind.ALLOCATION,
            amount=Decimal("1"),
            created_by=author.id,
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.fixture()
async def seeded(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, author) -> AsyncSession:
    """Run the seed against the test session instead of the application's own.

    The fund row is written here rather than by the seed, because since BE-10 (OBT-471)
    ``20260830_rr04`` owns it and the suite builds its schema with ``create_all``, which
    runs no migration. Arranging it is the honest translation of *the migration ran*, and
    the state the seed is entitled to expect; the refusal test below covers the other
    side.
    """
    db_session.add(RRFund(id=seed_script.CONFIRMED_FUND_ID, name="Shema Línguas"))
    await db_session.flush()

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(seed_script, "AsyncSessionLocal", _session)
    await seed_script.seed(author.email)
    return db_session


async def test_the_seed_refuses_an_author_it_cannot_find(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Refusing is the honest failure, and it has to be the loud one.

    The alternative a hurried fix reaches for is attaching the ten cards to whichever
    account is first, which is sample data making a claim about a real person — and the
    column that forces the question exists precisely because D1 said every request has
    an author.
    """

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(seed_script, "AsyncSessionLocal", _session)
    with pytest.raises(SystemExit):
        await seed_script.seed("ninguem@fixture.test")


async def test_the_seed_names_an_author_on_every_row_that_has_one(
    seeded: AsyncSession, author
) -> None:
    """Ten requests and two movements, and not one of them anonymous."""
    requests = (await seeded.execute(select(RRRequest))).scalars().all()
    movements = (await seeded.execute(select(RRFundMovement))).scalars().all()

    assert requests and movements
    assert {request.created_by for request in requests} == {author.id}
    assert {movement.created_by for movement in movements} == {author.id}


async def test_the_seed_writes_no_attendee_and_no_history(seeded: AsyncSession) -> None:
    """The two tables GATE-02 added stay empty, and that is the point.

    ``rr_evaluation_attendees`` records who was in the room and the two histories record
    who changed what. The seed held no meeting and edited nothing, so writing either
    would be exactly the fabricated data the invented ``solicitante`` names are careful
    not to be.
    """
    for model in (RREvaluationAttendee, RRRequestFieldHistory, RREvaluationFieldHistory):
        rows = (await seeded.execute(select(model))).scalars().all()
        assert rows == []


async def test_the_seed_writes_the_ten_cards_and_invents_no_fund(seeded: AsyncSession) -> None:
    """The fund count does not move: since BE-10 the seed writes cards, never funds.

    A fund row is an assertion about someone's money, which is exactly the assertion
    GATE-01 declined to make about the other four names — so a seed that grew one would
    be the fixture making it on the client's behalf.
    """
    funds = (await seeded.execute(select(RRFund))).scalars().all()
    assert {fund.id for fund in funds} == {seed_script.CONFIRMED_FUND_ID}
    assert all(fund.retired_at is None for fund in funds)

    requests = (await seeded.execute(select(RRRequest))).scalars().all()
    assert len(requests) == len(SEED_CARDS)


async def test_the_seed_refuses_a_database_that_was_not_migrated(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, author
) -> None:
    """Without the migration's row, seven cards would fail on a foreign key.

    Refusing by name is the ``_author`` shape: an ``IntegrityError`` names a constraint to
    somebody whose actual mistake was not running ``alembic upgrade head``.
    """

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(seed_script, "AsyncSessionLocal", _session)
    with pytest.raises(SystemExit):
        await seed_script.seed(author.email)


async def test_only_the_cards_in_triagem_carry_no_fund(seeded: AsyncSession) -> None:
    """Null is the state of a request the mesa has not assigned yet, never a gap.

    GATE-01 answered that the mesa assigns the fund at triage, so the two halves are one
    assertion: a card without a fund is in ``triagem``, and a card in ``triagem`` has no
    fund. The second half is the one that would rot silently — re-pointing a card and
    forgetting its column reads as data rather than as a bug.
    """
    requests = (await seeded.execute(select(RRRequest))).scalars().all()
    without = {request.id for request in requests if request.fund_id is None}
    in_triagem = {request.id for request in requests if request.stage is RRStage.TRIAGEM}

    assert without == in_triagem
    assert len(without) == 3
    assert {request.fund_id for request in requests} - {None} == {"linguas"}


async def test_no_approved_card_is_seeded_without_a_fund(seeded: AsyncSession) -> None:
    """BE-11's invariant, on the only rows that exist to break it.

    A request does not enter ``aprovado`` with no fund — the deduction would have no
    ledger to land in. It is a service rule and deliberately not a CHECK, because the
    same null is correct one column earlier, so the seed is where it is first honoured.
    """
    approved = (
        (await seeded.execute(select(RRRequest).where(RRRequest.stage == RRStage.APROVADO)))
        .scalars()
        .all()
    )
    assert approved
    assert all(request.fund_id is not None for request in approved)


async def test_the_seed_allocates_nothing_and_the_balance_says_so(seeded: AsyncSession) -> None:
    """The fund is born empty and the two approvals promise money nobody has put in.

    GATE-01 D6 has funds born at zero with the Gestores allocating, so the seed writes no
    ``ALLOCATION`` at all and the prototype's 480.000 stays a frontend dev fixture. The
    balance read through the service is therefore **-159.000** — the two approved cards'
    deductions against an empty fund — which is the negative-with-warning state D5 chose
    over a refusal, seeded on purpose rather than papered over.

    ``retired`` joined the tuple with BE-10 (OBT-471), and the exact comparison is what
    reported it — which is the argument for comparing the whole shape rather than the three
    figures: a field added to a balance read reaches this assertion before it reaches a
    screen.
    """
    kinds = (await seeded.execute(select(RRFundMovement.kind).distinct())).scalars().all()
    assert RRMovementKind.ALLOCATION not in kinds

    balances = await fund_balances(seeded)
    assert [balance._asdict() for balance in balances] == [
        {
            "id": "linguas",
            "name": "Shema Línguas",
            "retired": False,
            "allocated": Decimal("0.00"),
            "committed": Decimal("159000.00"),
            "available": Decimal("-159000.00"),
        }
    ]


async def test_the_seeded_scores_add_up_to_the_cards_total(seeded: AsyncSession) -> None:
    for card in SEED_CARDS:
        snapshot_id = f"rr-seed-snapshot-{card.n}"
        total = (
            await seeded.execute(
                select(func.sum(RREvaluationScore.score))
                .join(RREvaluation, RREvaluation.id == RREvaluationScore.evaluation_id)
                .where(RREvaluation.snapshot_id == snapshot_id)
            )
        ).scalar()
        assert total == card.score


async def test_the_seed_records_no_decision(seeded: AsyncSession) -> None:
    """A column does not imply a decision — the mesa moves cards without evaluating them."""
    decisions = (await seeded.execute(select(RREvaluation.decision))).scalars().all()
    assert decisions and all(decision is None for decision in decisions)


async def test_running_the_seed_twice_does_not_double_the_ledger(
    seeded: AsyncSession, author
) -> None:
    """The ledger is append-only, so a second run has nothing to correct with."""
    before = (await seeded.execute(select(func.sum(RRFundMovement.amount)))).scalar()

    await seed_script.seed(author.email)

    after = (await seeded.execute(select(func.sum(RRFundMovement.amount)))).scalar()
    assert after == before


def test_the_migration_writes_the_same_guard_the_models_do() -> None:
    """The append-only DDL has two homes on purpose, and this is what keeps them one rule.

    The migration spells the trigger out rather than importing it, because importing a
    model module executes ``app.core.database`` and builds an engine at import time — the
    reason 20260731_0001 already recorded. The cost of that is drift nothing would report:
    production runs the migration, pytest runs ``create_all``, and a trigger that grew
    apart would enforce differently in the two places without a single test going red.

    It is also the only reader the PostgreSQL branch of ``append_only_ddl`` has. The suite
    runs on SQLite, so nothing else here ever compiles the plpgsql that production uses.
    """
    spec = importlib.util.spec_from_file_location("_rr01", _REVISION)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.APPEND_ONLY_TABLES == (
        "rr_fund_movements",
        "rr_snapshots",
        "rr_request_field_history",
        "rr_evaluation_field_history",
    )

    for table in migration.APPEND_ONLY_TABLES:
        statements = append_only_ddl(table, "postgresql")
        assert statements[0] == migration.APPEND_ONLY_FUNCTION
        assert statements[1] == (
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION rr_reject_write()"
        )


async def test_a_snapshot_takes_one_evaluation_and_not_two(
    db_session: AsyncSession, evaluation: RREvaluation
) -> None:
    """GATE-02 D5 — *"a mesa quem decide"*, so one evaluation per snapshot.

    The constraint used to be ``(snapshot_id, evaluator_id)``, which allowed a snapshot
    any number of **unauthored** evaluations, because two NULLs are never equal in SQL.
    That was the floor both candidate answers shared, held while the gate was open; this
    test is the tightening, and it is written against exactly the row the old constraint
    let through.
    """
    db_session.add(RREvaluation(id="e2", snapshot_id=evaluation.snapshot_id))
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_a_request_cannot_be_written_without_an_author(
    db_session: AsyncSession,
) -> None:
    """D1 answered accounts, so there is no such thing as an unowned request.

    The trail of D7 is written about an owner, and a document with none is what the
    variant this column was nullable for would have produced.
    """
    db_session.add(
        RRRequest(id="sem-autor", request_type="traducao", stage="triagem", currency="BRL")
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.fixture()
async def request_history(
    db_session: AsyncSession, evaluation: RREvaluation, author
) -> RRRequestFieldHistory:
    row = RRRequestFieldHistory(
        id="h1",
        request_id="r1",
        field_key="reg_name",
        old_value="",
        new_value="Matsés",
        changed_by=author.id,
    )
    db_session.add(row)
    await db_session.commit()
    return row


async def test_a_history_row_cannot_be_rewritten(
    db_session: AsyncSession, request_history: RRRequestFieldHistory
) -> None:
    """A trail whose rows can be edited answers nothing, so it takes the ledger's trigger.

    Written through the connection rather than the ORM: the point is that the *database*
    refuses, not that a service remembered to.
    """
    with pytest.raises(DatabaseError):
        await db_session.execute(
            text("UPDATE rr_request_field_history SET new_value = 'outro' WHERE id = :id"),
            {"id": request_history.id},
        )


async def test_a_history_row_cannot_be_deleted(
    db_session: AsyncSession, request_history: RRRequestFieldHistory
) -> None:
    with pytest.raises(DatabaseError):
        await db_session.execute(
            text("DELETE FROM rr_request_field_history WHERE id = :id"),
            {"id": request_history.id},
        )


async def test_a_score_change_records_both_sides(
    db_session: AsyncSession, evaluation: RREvaluation, author
) -> None:
    """D7's own example — *quem subiu uma nota de 2 para 5* — needs both sides stored.

    ``field_key`` is the criterion key the scores table already uses, so a trail row and
    a score row name the criterion the same way and nothing translates between them.
    """
    db_session.add(
        RREvaluationFieldHistory(
            id="eh1",
            evaluation_id=evaluation.id,
            field_key="traducao_orcamento",
            old_value="2",
            new_value="5",
            changed_by=author.id,
        )
    )
    await db_session.commit()

    stored = await db_session.get(RREvaluationFieldHistory, "eh1")
    assert stored is not None
    assert (stored.old_value, stored.new_value) == ("2", "5")
    assert stored.changed_by == author.id


async def test_the_room_is_a_list_and_the_signature_is_one_person(
    db_session: AsyncSession, evaluation: RREvaluation, author
) -> None:
    """D5 asked for two records, and neither derives from the other.

    ``evaluator_id`` is who signed on behalf of the mesa; the attendees are who was in
    the room. A member appears in the second without being the first, which is the whole
    reason it is a table and not a column.
    """
    outro = await make_user(db_session, email="presente@fixture.test")
    db_session.add_all(
        [
            RREvaluationAttendee(evaluation_id=evaluation.id, user_id=author.id),
            RREvaluationAttendee(evaluation_id=evaluation.id, user_id=outro.id),
        ]
    )
    await db_session.commit()

    present = (
        (
            await db_session.execute(
                select(RREvaluationAttendee).where(
                    RREvaluationAttendee.evaluation_id == evaluation.id
                )
            )
        )
        .scalars()
        .all()
    )
    assert {row.user_id for row in present} == {author.id, outro.id}
    assert evaluation.evaluator_id is None


def test_rr_funds_never_grew_a_balance_or_an_editor() -> None:
    """BE-15 audits everything and still adds nothing here, and that is the assertion.

    GATE-01 D6's literal reading — an editable *alocado* carrying ``updated_by`` and
    ``updated_at`` — is the trap this test closes: the money's own trail is **already**
    BE-07's ledger, ``rr_fund_movements``, append-only in the database, where every
    ALLOCATION names its author and its instant. A wrong allocation is corrected by a
    compensating movement, never by an UPDATE (contract §3.3) — so an ``allocated``
    column would store a derived number, and ``updated_by``/``updated_at`` would audit
    edits the design forbids from existing. The day this test goes red, the ledger is
    being bypassed, not extended.
    """
    columns = set(RRFund.__table__.columns.keys())

    assert columns == {"id", "name", "provisional", "created_at"}
    assert not columns & {"allocated", "updated_by", "updated_at"}


def test_a_total_is_spread_without_breaking_the_range() -> None:
    for total in range(31):
        scores = _spread(total)
        assert len(scores) == 6
        assert sum(scores) == total
        assert all(0 <= score <= 5 for score in scores)
