"""The alocado's write path (BE-09, OBT-469): edits become ledger entries, never columns.

GATE-01 D6's "campo editável" is the screen; here it is proven to be nothing but
``ALLOCATION`` movements and their compensations in BE-07's append-only ledger. The three
DoD items this endpoint may not break — the movement carrying its own authorship, the
absence of ``allocated``/``updated_by``/``updated_at``, the correction as a compensating
movement — are BE-07's contract; what its base pins as behaviour (the update-refusing
trigger in ``test_schema.py``, the writers' refusals in ``test_funds.py``) is not
re-asserted here. This file adds the endpoint's own half: what each edit writes, the two
value validations, the ``allocate_funds`` gate, and the read FE-26 renders — plus the one
schema pin the DoD asks for that the base did not carry as a test, the exact column set of
``rr_funds``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.db.models.resource_request import RRFund, RRFundMovement, RRMovementKind
from app.services.resource_request import set_allocation
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

ALLOCATION = "/api/resource-requests/funds/linguas/allocation"


@pytest.fixture()
async def fund(db_session: AsyncSession) -> RRFund:
    row = RRFund(id="linguas", name="Shema Línguas")
    db_session.add(row)
    await db_session.commit()
    return row


async def as_role(db_session, rrf_app, role_key: str, email: str):
    user = await make_user(db_session, email=email)
    await grant(db_session, user, rrf_app, role_key)
    return user, await auth_header(db_session, user)


async def ledger(db_session: AsyncSession) -> list[RRFundMovement]:
    rows = await db_session.execute(
        select(RRFundMovement).order_by(RRFundMovement.created_at, RRFundMovement.id)
    )
    return list(rows.scalars().all())


# ——— what an edit writes ————————————————————————————————————————————————————————


async def test_a_raise_is_one_allocation_carrying_the_authors_own_mark(
    db_session, client, rrf_app, fund
) -> None:
    """DoD 1: the movement's ``created_by``/``created_at``/``reason`` are D6's who-and-when."""
    gestor, headers = await as_role(db_session, rrf_app, "gestor", "gestora@rrf.test")

    answer = await client.put(
        ALLOCATION,
        headers=headers,
        json={"amount": "480000.00", "reason": "abertura do ciclo"},
    )

    assert answer.status_code == 200
    body = answer.json()
    assert Decimal(body["allocated"]) == Decimal("480000.00")
    assert body["allocated_by"] == "gestora@rrf.test"
    assert body["allocated_at"] is not None

    movements = await ledger(db_session)
    assert len(movements) == 1
    entry = movements[0]
    assert entry.kind is RRMovementKind.ALLOCATION
    assert entry.amount == Decimal("480000.00")
    assert entry.created_by == gestor.id
    assert entry.created_at is not None
    assert entry.reason == "abertura do ciclo"


async def test_the_payload_cannot_name_an_author(db_session, client, rrf_app, fund) -> None:
    """Who edited comes from the session; a payload that could carry it could lie."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora2@rrf.test")

    answer = await client.put(
        ALLOCATION,
        headers=headers,
        json={"amount": "10.00", "created_by": "outra-pessoa"},
    )

    assert answer.status_code == 422


async def test_a_second_raise_moves_only_the_difference(db_session, client, rrf_app, fund) -> None:
    """The field states a value, never a delta: 1000 then 1500 allocates 1000 and 500."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora3@rrf.test")

    await client.put(ALLOCATION, headers=headers, json={"amount": "1000.00"})
    answer = await client.put(ALLOCATION, headers=headers, json={"amount": "1500.00"})

    assert Decimal(answer.json()["allocated"]) == Decimal("1500.00")
    movements = await ledger(db_session)
    assert all(m.kind is RRMovementKind.ALLOCATION for m in movements)
    assert sorted(m.amount for m in movements) == [Decimal("500.00"), Decimal("1000.00")]


async def test_saying_the_same_value_again_writes_nothing(
    db_session, client, rrf_app, fund
) -> None:
    """Re-saving an unchanged field must not fabricate an edit in the ledger."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora4@rrf.test")

    await client.put(ALLOCATION, headers=headers, json={"amount": "1000.00"})
    answer = await client.put(ALLOCATION, headers=headers, json={"amount": "1000.00"})

    assert answer.status_code == 200
    assert len(await ledger(db_session)) == 1


async def test_lowering_is_a_full_reversal_plus_a_new_entry(
    db_session, client, rrf_app, fund
) -> None:
    """DoD 3, this endpoint's half: the correction names what it compensates through
    ``reverses_id`` and leaves the corrected row exactly as written — the trigger that
    makes an UPDATE impossible at all is BE-07's, pinned in ``test_schema.py``."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora5@rrf.test")

    await client.put(ALLOCATION, headers=headers, json={"amount": "1000.00"})
    answer = await client.put(
        ALLOCATION, headers=headers, json={"amount": "600.00", "reason": "corrigindo"}
    )

    assert Decimal(answer.json()["allocated"]) == Decimal("600.00")

    movements = await ledger(db_session)
    assert len(movements) == 3
    allocations = [m for m in movements if m.kind is RRMovementKind.ALLOCATION]
    reversals = [m for m in movements if m.kind is RRMovementKind.REVERSAL]
    original = next(m for m in allocations if m.amount == Decimal("1000.00"))
    reentry = next(m for m in allocations if m.amount == Decimal("600.00"))
    assert original.reverses_id is None
    assert [(r.reverses_id, r.amount) for r in reversals] == [(original.id, Decimal("1000.00"))]
    assert reentry.reason == "corrigindo"


async def test_lowering_to_zero_marks_the_corrector_not_the_corrected(
    db_session, client, rrf_app, fund
) -> None:
    """A correction down to zero writes only reversals, and the mark must follow them:
    naming the Gestor whose entry was just corrected away would be the opposite of D6."""
    antiga = await make_user(db_session, email="antiga@rrf.test")
    db_session.add(
        RRFundMovement(
            fund_id="linguas",
            kind=RRMovementKind.ALLOCATION,
            amount=Decimal("1000.00"),
            reason="entrada antiga",
            created_by=antiga.id,
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
    )
    await db_session.commit()

    _, headers = await as_role(db_session, rrf_app, "gestor", "corretora@rrf.test")
    answer = await client.put(ALLOCATION, headers=headers, json={"amount": "0.00"})

    body = answer.json()
    assert Decimal(body["allocated"]) == Decimal("0.00")
    assert body["allocated_by"] == "corretora@rrf.test"

    movements = await ledger(db_session)
    assert [m.kind for m in movements] == [RRMovementKind.ALLOCATION, RRMovementKind.REVERSAL]


# ——— the two value validations ———————————————————————————————————————————————————


async def test_zero_on_a_newborn_fund_is_valid_and_fabricates_no_edit(
    db_session, client, rrf_app, fund
) -> None:
    """DoD: funds are born at zero (D6), so zero is a value and never a refusal — and a
    save that changed nothing writes no authored movement, because ``append_movement``
    rightly refuses a movement that moves nothing."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora6@rrf.test")

    answer = await client.put(ALLOCATION, headers=headers, json={"amount": "0"})

    assert answer.status_code == 200
    body = answer.json()
    assert Decimal(body["allocated"]) == Decimal("0.00")
    assert body["allocated_by"] is None
    assert body["allocated_at"] is None
    assert await ledger(db_session) == []


async def test_a_negative_amount_is_refused_where_the_field_is(
    db_session, client, rrf_app, fund
) -> None:
    """DoD: refused with a decidable answer — the module's field-located 422."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora7@rrf.test")

    answer = await client.put(ALLOCATION, headers=headers, json={"amount": "-100.00"})

    assert answer.status_code == 422
    assert any("amount" in error["loc"] for error in answer.json()["detail"])
    assert await ledger(db_session) == []


async def test_the_service_refuses_a_negative_on_its_own(db_session, fund) -> None:
    """The wire refusal is Pydantic's; the service guards callers inside the process."""
    author = await make_user(db_session, email="direto@rrf.test")
    with pytest.raises(ValidationError):
        await set_allocation(
            db_session,
            fund_id="linguas",
            amount=Decimal("-1.00"),
            author_id=author.id,
            reason="",
        )


async def test_money_that_does_not_fit_the_column_is_refused(
    db_session, client, rrf_app, fund
) -> None:
    """First place a client POSTs money straight into ``Numeric(14, 2)``: a third decimal
    and a thirteenth integer digit are refused, not rounded — BE-05's rule. ``1E+30``
    and ``NaN`` are the §8.5 fixtures, the values whose *refusal arithmetic* can blow:
    each must come out as the module's 422, never a 500."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora8@rrf.test")

    for amount in ("10.001", "1000000000000.00", "1E+30", "NaN"):
        answer = await client.put(ALLOCATION, headers=headers, json={"amount": amount})
        assert answer.status_code == 422, amount


# ——— the gate ————————————————————————————————————————————————————————————————————


async def test_only_the_gestor_writes_an_allocation(db_session, client, rrf_app, fund) -> None:
    """GATE-01 D6: ``allocate_funds`` and never ``manage_funds`` — the mesa holds the
    Painel's door and still may not put money in a fund."""
    for role, email in (("mesa", "mesa-aloca@rrf.test"), ("equipe", "equipe-aloca@rrf.test")):
        _, headers = await as_role(db_session, rrf_app, role, email)
        answer = await client.put(ALLOCATION, headers=headers, json={"amount": "10.00"})
        assert answer.status_code == 403, role

    assert await ledger(db_session) == []


async def test_the_read_is_painel_surface(db_session, client, rrf_app, fund) -> None:
    """``manage_funds`` on the read: mesa and Gestor see who allocated; a team does not."""
    for role, email, expected in (
        ("mesa", "mesa-le@rrf.test", 200),
        ("gestor", "gestor-le@rrf.test", 200),
        ("equipe", "equipe-le@rrf.test", 403),
    ):
        _, headers = await as_role(db_session, rrf_app, role, email)
        answer = await client.get(ALLOCATION, headers=headers)
        assert answer.status_code == expected, role


# ——— the read and the unknowns ———————————————————————————————————————————————————


async def test_the_read_answers_the_sum_and_the_last_mark(
    db_session, client, rrf_app, fund
) -> None:
    """DoD: the alocado summed plus author and stamp of the latest allocation entry."""
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora9@rrf.test")
    await client.put(ALLOCATION, headers=headers, json={"amount": "250.00"})

    answer = await client.get(ALLOCATION, headers=headers)

    body = answer.json()
    assert Decimal(body["allocated"]) == Decimal("250.00")
    assert body["fund_id"] == "linguas"
    assert body["allocated_by"] == "gestora9@rrf.test"
    assert body["allocated_at"] is not None


async def test_an_unknown_fund_answers_404_on_both_verbs(db_session, client, rrf_app, fund) -> None:
    _, headers = await as_role(db_session, rrf_app, "gestor", "gestora10@rrf.test")
    missing = "/api/resource-requests/funds/nada/allocation"

    assert (await client.get(missing, headers=headers)).status_code == 404
    assert (await client.put(missing, headers=headers, json={"amount": "10.00"})).status_code == 404


# ——— the schema pin the DoD asks for ————————————————————————————————————————————


def test_rr_funds_still_has_no_allocated_and_no_editor_columns() -> None:
    """DoD 2: the literal reading of D6 — ``allocated`` + ``updated_by`` + ``updated_at``
    on ``rr_funds`` — must stay unbuilt, or *store two, derive the third* breaks and a
    second audit design stands up against GATE-02 D7's. The base pinned it in the model's
    own docstring; this is the pin as a test, exact so a new balance column of any name
    fails it. BE-10 (OBT-471) traded ``provisional`` for ``retired_at`` inside the same
    exact set, which is what an exact set is for: a life-cycle flag passes review, a
    balance column cannot slip in beside it."""
    assert {column.name for column in RRFund.__table__.columns} == {
        "id",
        "name",
        "retired_at",
        "created_at",
    }
