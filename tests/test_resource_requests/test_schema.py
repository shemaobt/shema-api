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
    RREvaluationScore,
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRSnapshot,
    append_only_ddl,
)
from scripts.seed_resource_requests import SEED_CARDS, SEED_FUNDS, _spread

_REVISION = (
    Path(__file__).resolve().parents[2]
    / "alembic"
    / "versions"
    / "20260825_rr01_resource_request_module.py"
)


@pytest.fixture()
async def fund(db_session: AsyncSession) -> RRFund:
    row = RRFund(id="linguas", name="Shema Línguas")
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def movement(db_session: AsyncSession, fund: RRFund) -> RRFundMovement:
    row = RRFundMovement(
        id="m1", fund_id=fund.id, kind=RRMovementKind.ALLOCATION, amount=Decimal("480000")
    )
    db_session.add(row)
    await db_session.commit()
    return row


@pytest.fixture()
async def evaluation(db_session: AsyncSession) -> RREvaluation:
    """Flushed one table at a time, because request and snapshot reference each other.

    ``rr_requests.revision_of_id`` points at a snapshot and ``rr_snapshots.request_id``
    points back, and no ``relationship()`` tells the unit of work which way to break the
    tie — so a single flush is free to write the evaluation before its snapshot exists.
    """
    db_session.add(RRRequest(id="r1", request_type="traducao", stage="triagem", currency="BRL"))
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


async def test_a_movement_against_an_unknown_fund_is_refused(db_session: AsyncSession) -> None:
    db_session.add(
        RRFundMovement(
            id="m3", fund_id="nao-existe", kind=RRMovementKind.ALLOCATION, amount=Decimal("1")
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


@pytest.fixture()
async def seeded(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> AsyncSession:
    """Run the seed against the test session instead of the application's own."""

    @asynccontextmanager
    async def _session():
        yield db_session

    monkeypatch.setattr(seed_script, "AsyncSessionLocal", _session)
    await seed_script.seed()
    return db_session


async def test_the_seed_writes_the_five_funds_and_the_ten_cards(seeded: AsyncSession) -> None:
    funds = (await seeded.execute(select(RRFund))).scalars().all()
    assert {fund.id for fund in funds} == {fund_id for fund_id, _name, _alloc in SEED_FUNDS}
    assert all(fund.provisional for fund in funds), "GATE-01 has not confirmed the names"

    requests = (await seeded.execute(select(RRRequest))).scalars().all()
    assert len(requests) == len(SEED_CARDS)


async def test_the_seeded_balances_are_the_prototypes(seeded: AsyncSession) -> None:
    """Alocado and comprometido as sums over the ledger, never as columns."""
    totals = (
        await seeded.execute(
            select(
                RRFundMovement.fund_id, RRFundMovement.kind, func.sum(RRFundMovement.amount)
            ).group_by(RRFundMovement.fund_id, RRFundMovement.kind)
        )
    ).all()
    by_kind = {(fund_id, kind): amount for fund_id, kind, amount in totals}

    for fund_id, _name, allocated in SEED_FUNDS:
        assert by_kind[(fund_id, RRMovementKind.ALLOCATION)] == allocated

    committed = {
        fund_id: amount
        for (fund_id, kind), amount in by_kind.items()
        if kind is RRMovementKind.APPROVAL_DEDUCTION
    }
    assert committed == {"linguas": Decimal("128000"), "pesquisa": Decimal("31000")}


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


async def test_running_the_seed_twice_does_not_double_the_ledger(seeded: AsyncSession) -> None:
    """The ledger is append-only, so a second run has nothing to correct with."""
    before = (await seeded.execute(select(func.sum(RRFundMovement.amount)))).scalar()

    await seed_script.seed()

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

    assert migration.APPEND_ONLY_TABLES == ("rr_fund_movements", "rr_snapshots")

    for table in migration.APPEND_ONLY_TABLES:
        statements = append_only_ddl(table, "postgresql")
        assert statements[0] == migration.APPEND_ONLY_FUNCTION
        assert statements[1] == (
            f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION rr_reject_write()"
        )


def test_a_total_is_spread_without_breaking_the_range() -> None:
    for total in range(31):
        scores = _spread(total)
        assert len(scores) == 6
        assert sum(scores) == total
        assert all(0 <= score <= 5 for score in scores)
