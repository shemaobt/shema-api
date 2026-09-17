"""The ledger: append-only movements, balances as sums, and the read surface over both.

The property under everything here is one sentence — **a balance is a sum over the
ledger, and nothing else** — and the randomized test is where it is held against
sequences nobody sat down and designed. The rest is the shape of the rules around it:
what the two writers refuse, that neither commits the caller's transaction (the contract
BE-08's stage-change-plus-movement atomicity is built on), and who may read money at all.

What is deliberately **not** here is the double-approve serialization:
``with_for_update()`` compiles to nothing on SQLite, silently, so that test lives in
``test_ledger_concurrency.py`` behind a PostgreSQL URL (design §7.3).
"""

from __future__ import annotations

import random
from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    UnknownReferenceError,
    ValidationError,
)
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind, RRRequest
from app.services.resource_request import (
    append_movement,
    fund_balances,
    movements_of_fund,
    movements_of_request,
    reverse_movement,
)
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

FUNDS = "/api/resource-requests/funds"


@pytest.fixture()
async def author(db_session: AsyncSession):
    return await make_user(db_session, email="autora@ledger.test")


@pytest.fixture()
async def fund(db_session: AsyncSession) -> RRFund:
    row = RRFund(id="linguas", name="Shema Línguas")
    db_session.add(row)
    await db_session.commit()
    return row


async def as_role(db_session, rrf_app, role_key: str, email: str) -> dict[str, str]:
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, role_key)
    return await auth_header(db_session, user)


# ——— the writers ————————————————————————————————————————————————————————————————


async def test_a_movement_that_moves_nothing_is_refused(db_session, fund, author) -> None:
    """Direction comes from the kind, so an amount is a magnitude and zero says nothing."""
    for amount in (Decimal("0"), Decimal("-10.00")):
        with pytest.raises(ValidationError):
            await append_movement(
                db_session,
                fund_id=fund.id,
                kind=RRMovementKind.ALLOCATION,
                amount=amount,
                author_id=author.id,
                reason="nada",
            )


async def test_an_amount_that_does_not_fit_the_column_is_refused(db_session, fund, author) -> None:
    """The BE-05 rule at the ledger's own door, and each shape a refusal rather than a 500.

    A sub-cent amount would be rounded into ``Numeric(14, 2)`` by PostgreSQL and stored as
    sent by SQLite — a movement that sums differently per dialect. ``NaN`` is the sharper
    trap: comparing it raises ``InvalidOperation``, which Pydantic does not convert and no
    handler renders, so without the guard it would be the one input answered with a stack
    trace.
    """
    for amount in (Decimal("10.999"), Decimal("1E+30"), Decimal("NaN")):
        with pytest.raises(ValidationError):
            await append_movement(
                db_session,
                fund_id=fund.id,
                kind=RRMovementKind.ALLOCATION,
                amount=amount,
                author_id=author.id,
                reason="não cabe",
            )


async def test_a_movement_against_an_unknown_fund_is_refused(db_session, author) -> None:
    with pytest.raises(UnknownReferenceError):
        await append_movement(
            db_session,
            fund_id="ready",
            kind=RRMovementKind.ALLOCATION,
            amount=Decimal("100.00"),
            author_id=author.id,
            reason="fundo que a GATE-01 aposentou",
        )


async def test_the_generic_writer_refuses_a_reversal(db_session, fund, author) -> None:
    """A compensation copies what it compensates; a kind that let the caller state the
    amount would let it mis-state exactly what a compensating movement may not."""
    with pytest.raises(ValidationError):
        await append_movement(
            db_session,
            fund_id=fund.id,
            kind=RRMovementKind.REVERSAL,
            amount=Decimal("100.00"),
            author_id=author.id,
            reason="por fora",
        )


async def test_a_reversal_compensates_exactly_and_names_its_movement(
    db_session, fund, author
) -> None:
    moved = await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.ALLOCATION,
        amount=Decimal("480000.00"),
        author_id=author.id,
        reason="alocação errada",
    )
    await db_session.commit()

    correction = await reverse_movement(
        db_session, movement_id=moved.id, author_id=author.id, reason="correção"
    )
    await db_session.commit()

    assert correction.kind is RRMovementKind.REVERSAL
    assert correction.reverses_id == moved.id
    assert correction.amount == moved.amount
    assert correction.fund_id == moved.fund_id
    assert correction.currency == moved.currency
    assert correction.created_by == author.id

    balance = (await fund_balances(db_session))[0]
    assert balance.allocated == Decimal("0.00")
    assert balance.available == Decimal("0.00")


async def test_a_reversal_is_not_reversed(db_session, fund, author) -> None:
    """Re-applying what a wrong reversal undid is a new movement of the original kind —
    a chain of negations would have to be resolved before any row meant anything."""
    moved = await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.COMMITMENT,
        amount=Decimal("50.00"),
        author_id=author.id,
        reason="compromisso",
    )
    correction = await reverse_movement(
        db_session, movement_id=moved.id, author_id=author.id, reason="correção"
    )
    await db_session.commit()

    with pytest.raises(ValidationError):
        await reverse_movement(
            db_session, movement_id=correction.id, author_id=author.id, reason="des-correção"
        )


async def test_a_movement_is_not_reversed_twice(db_session, fund, author) -> None:
    """Compensating twice over-corrects: un-approve twice must not restore twice."""
    moved = await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.APPROVAL_DEDUCTION,
        amount=Decimal("70.00"),
        author_id=author.id,
        reason="aprovação",
    )
    await reverse_movement(
        db_session, movement_id=moved.id, author_id=author.id, reason="des-aprovação"
    )
    await db_session.commit()

    with pytest.raises(ConflictError):
        await reverse_movement(
            db_session, movement_id=moved.id, author_id=author.id, reason="de novo"
        )


async def test_reversing_an_unknown_movement_is_refused(db_session, fund, author) -> None:
    with pytest.raises(UnknownReferenceError):
        await reverse_movement(
            db_session, movement_id="nunca-existiu", author_id=author.id, reason="nada"
        )


async def test_the_writers_leave_the_transaction_to_the_caller(db_session, fund, author) -> None:
    """Flushed and not committed — the contract BE-08's atomicity is built on.

    A stage change and the movement it causes must commit or roll back together, which is
    only possible if appending does not close the transaction under the caller. Rolling
    back after a successful append must therefore leave no trace.
    """
    await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.APPROVAL_DEDUCTION,
        amount=Decimal("100.00"),
        author_id=author.id,
        reason="vai ser desfeito",
    )
    await db_session.rollback()

    count = (await db_session.execute(select(func.count()).select_from(RRFundMovement))).scalar()
    assert count == 0


# ——— balances are sums, whatever the sequence ————————————————————————————————————


async def test_the_balances_agree_with_any_sequence_of_movements(
    db_session, client, rrf_app, author
) -> None:
    """The property the DoD asks for: over random sequences, the balance endpoint equals
    an independent fold of the same movements.

    The fold below is written from the rule's statement — an allocation raises *alocado*,
    a commitment or approval deduction raises *comprometido*, a reversal lowers the bucket
    of the movement it names — and never from the SQL, so the two can disagree. The
    comparison runs twice, against the service and against ``GET /funds``, so the wire —
    where ``Decimal`` becomes a string — is held to the same sums. Amounts are whole
    numbers because the suite runs on SQLite, which stores ``Numeric`` as float: integers
    stay exact there, and what is under test is the bucket arithmetic, not decimal
    storage — the PostgreSQL path exercises real ``numeric``.
    """
    rng = random.Random(456)
    fund_ids = ["fundo-a", "fundo-b", "fundo-c"]
    for fund_id in fund_ids:
        db_session.add(RRFund(id=fund_id, name=f"Fundo {fund_id[-1]}"))
    await db_session.commit()

    expected: dict[str, dict[str, Decimal]] = {
        fund_id: {"allocated": Decimal("0.00"), "committed": Decimal("0.00")}
        for fund_id in fund_ids
    }
    reversible: list[tuple[str, str, RRMovementKind, Decimal]] = []
    kinds = [
        RRMovementKind.ALLOCATION,
        RRMovementKind.COMMITMENT,
        RRMovementKind.APPROVAL_DEDUCTION,
    ]

    def bucket_of(kind: RRMovementKind) -> str:
        return "allocated" if kind is RRMovementKind.ALLOCATION else "committed"

    for _ in range(150):
        if reversible and rng.random() < 0.3:
            movement_id, fund_id, kind, amount = reversible.pop(rng.randrange(len(reversible)))
            await reverse_movement(
                db_session, movement_id=movement_id, author_id=author.id, reason="correção"
            )
            expected[fund_id][bucket_of(kind)] -= amount
        else:
            fund_id = rng.choice(fund_ids)
            kind = rng.choice(kinds)
            amount = Decimal(rng.randrange(1, 500_000))
            movement = await append_movement(
                db_session,
                fund_id=fund_id,
                kind=kind,
                amount=amount,
                author_id=author.id,
                reason="sequência aleatória",
            )
            reversible.append((movement.id, fund_id, kind, amount))
            expected[fund_id][bucket_of(kind)] += amount
    await db_session.commit()

    balances = {balance.id: balance for balance in await fund_balances(db_session)}
    assert set(balances) == set(fund_ids)
    for fund_id in fund_ids:
        assert balances[fund_id].allocated == expected[fund_id]["allocated"]
        assert balances[fund_id].committed == expected[fund_id]["committed"]
        assert balances[fund_id].available == (
            expected[fund_id]["allocated"] - expected[fund_id]["committed"]
        )

    headers = await as_role(db_session, rrf_app, "mesa", "mesa-prop@ledger.test")
    res = await client.get(FUNDS, headers=headers)
    assert res.status_code == 200, res.text
    cards = {card["id"]: card for card in res.json()}
    assert set(cards) == set(fund_ids)
    for fund_id in fund_ids:
        assert Decimal(cards[fund_id]["allocated"]) == expected[fund_id]["allocated"]
        assert Decimal(cards[fund_id]["committed"]) == expected[fund_id]["committed"]
        assert Decimal(cards[fund_id]["available"]) == (
            expected[fund_id]["allocated"] - expected[fund_id]["committed"]
        )


async def test_a_fund_with_no_movements_answers_three_zeros(db_session, fund) -> None:
    """The state every fund is born in since GATE-01 D6."""
    balance = (await fund_balances(db_session))[0]
    assert (balance.allocated, balance.committed, balance.available) == (
        Decimal("0.00"),
        Decimal("0.00"),
        Decimal("0.00"),
    )


# ——— the read surface ————————————————————————————————————————————————————————————


async def test_the_balance_endpoint_agrees_with_the_ledger(
    db_session, client, rrf_app, fund, author
) -> None:
    await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.ALLOCATION,
        amount=Decimal("1000.00"),
        author_id=author.id,
        reason="alocação",
    )
    committed = await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.COMMITMENT,
        amount=Decimal("200.00"),
        author_id=author.id,
        reason="compromisso",
    )
    await append_movement(
        db_session,
        fund_id=fund.id,
        kind=RRMovementKind.APPROVAL_DEDUCTION,
        amount=Decimal("500.00"),
        author_id=author.id,
        reason="aprovação",
    )
    await reverse_movement(
        db_session, movement_id=committed.id, author_id=author.id, reason="correção"
    )
    await db_session.commit()

    headers = await as_role(db_session, rrf_app, "mesa", "mesa@ledger.test")
    res = await client.get(FUNDS, headers=headers)
    assert res.status_code == 200, res.text

    (card,) = res.json()
    assert card["id"] == fund.id
    assert card["name"] == fund.name
    assert Decimal(card["allocated"]) == Decimal("1000.00")
    assert Decimal(card["committed"]) == Decimal("500.00")
    assert Decimal(card["available"]) == Decimal("500.00")


async def test_the_history_reads_by_fund_and_by_request(
    db_session, client, rrf_app, author
) -> None:
    """The DoD's two axes, each answering only its own rows."""
    for fund_id, name in (("fundo-a", "Fundo A"), ("fundo-b", "Fundo B")):
        db_session.add(RRFund(id=fund_id, name=name))
    request = RRRequest(request_type="traducao", created_by=author.id)
    db_session.add(request)
    await db_session.commit()

    on_a = await append_movement(
        db_session,
        fund_id="fundo-a",
        kind=RRMovementKind.APPROVAL_DEDUCTION,
        amount=Decimal("300.00"),
        author_id=author.id,
        reason="aprovação",
        request_id=request.id,
    )
    on_b = await append_movement(
        db_session,
        fund_id="fundo-b",
        kind=RRMovementKind.ALLOCATION,
        amount=Decimal("900.00"),
        author_id=author.id,
        reason="alocação",
    )
    restored = await reverse_movement(
        db_session, movement_id=on_a.id, author_id=author.id, reason="des-aprovação"
    )
    await db_session.commit()

    headers = await as_role(db_session, rrf_app, "gestor", "gestor@ledger.test")

    by_fund = await client.get(f"{FUNDS}/fundo-a/movements", headers=headers)
    assert by_fund.status_code == 200, by_fund.text
    assert {row["id"] for row in by_fund.json()} == {on_a.id, restored.id}

    by_request = await client.get(
        f"/api/resource-requests/requests/{request.id}/movements", headers=headers
    )
    assert by_request.status_code == 200, by_request.text
    assert {row["id"] for row in by_request.json()} == {on_a.id, restored.id}
    assert {row["fund_id"] for row in by_request.json()} == {"fundo-a"}

    lone = await client.get(f"{FUNDS}/fundo-b/movements", headers=headers)
    (entry,) = lone.json()
    assert entry["id"] == on_b.id
    assert entry["kind"] == "allocation"
    assert Decimal(entry["amount"]) == Decimal("900.00")
    assert entry["created_by"] == author.id
    assert entry["reason"] == "alocação"
    assert entry["created_at"] is not None


async def test_an_unknown_fund_or_request_history_is_a_404(db_session, client, rrf_app) -> None:
    headers = await as_role(db_session, rrf_app, "mesa", "mesa404@ledger.test")

    assert (await client.get(f"{FUNDS}/ready/movements", headers=headers)).status_code == 404
    assert (
        await client.get("/api/resource-requests/requests/nada/movements", headers=headers)
    ).status_code == 404


async def test_a_team_does_not_read_money(db_session, client, rrf_app, fund, author) -> None:
    """GATE-03 D4: a team follows its own request's status, never the ledger behind it.

    The three routes gate on ``manage_funds``, and the by-request history is the cell
    that would rot: it lives on a ``/requests/…`` path, and ``edit_requests`` — which a
    team does hold — is one habit away from being the guard someone reaches for.
    """
    request = RRRequest(request_type="traducao", created_by=author.id)
    db_session.add(request)
    await db_session.commit()

    headers = await as_role(db_session, rrf_app, "equipe", "equipe@ledger.test")

    for path in (
        FUNDS,
        f"{FUNDS}/{fund.id}/movements",
        f"/api/resource-requests/requests/{request.id}/movements",
    ):
        res = await client.get(path, headers=headers)
        assert res.status_code == 403, f"{path}: {res.status_code}"


async def test_the_history_services_refuse_unknown_ids_themselves(db_session, fund) -> None:
    """The 404 above is the service's own ``NotFoundError``, not a route's improvisation.

    These are read outside HTTP eventually — BE-08 reading history inside its transaction
    — so the refusal has to be the module's exception, rendered by the global handler,
    and not a shape only a route knows how to produce.
    """
    with pytest.raises(NotFoundError):
        await movements_of_fund(db_session, "ready")
    with pytest.raises(NotFoundError):
        await movements_of_request(db_session, "nada")
