"""The fund's life cycle (BE-10, OBT-471): created, renamed, retired — never deleted.

GATE-01 D1 left four of PRD v1.1 §3's names undecided and the client asked for an editable
fund area, which is the real answer to *decide later*: he types instead of us guessing. So
a fund stops being a seed line and becomes a row somebody creates, and this file pins the
five things that answer has to keep true — the id is the server's and opaque, the name is
the only identity and is unique, retiring hides without deleting, retiring refuses under a
live request with the count, and every one of the three is the Gestor's alone.

What is deliberately *not* re-asserted here is the ledger's own contract (BE-07) and the
alocado's write path (BE-09): retirement does not touch money, and a test that checked it
did would be describing a coupling this issue was careful not to build.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.db.models.resource_request import (
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRStage,
)
from app.services.resource_request import (
    RESERVED_FUND_NAMES,
    create_fund,
    fund_balances,
    rename_fund,
    retire_fund,
)
from tests.baker import make_user
from tests.test_resource_requests.conftest import auth_header, grant

FUNDS = "/api/resource-requests/funds"


@pytest.fixture()
async def author(db_session: AsyncSession):
    return await make_user(db_session, email="autora@fundos.test")


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


async def a_request(db_session: AsyncSession, author, *, id: str, stage: RRStage, fund_id: str):
    db_session.add(
        RRRequest(
            id=id,
            request_type="traducao",
            stage=stage,
            currency="BRL",
            fund_id=fund_id,
            created_by=author.id,
        )
    )
    await db_session.commit()


# ——— creating ————————————————————————————————————————————————————————————————————


async def test_the_server_mints_an_opaque_id_and_the_name_is_all_the_caller_says(
    db_session: AsyncSession,
) -> None:
    """DoD: ``uuid4().hex``, never a slug, never the client's.

    A slug is the shape a reader reaches for first and it breaks on the next DoD line:
    renaming may not touch the id, and a slug would keep the old name legible inside every
    ledger entry citing the fund forever.
    """
    fund = await create_fund(db_session, name="Shema BTAT")

    assert fund.name == "Shema BTAT"
    assert len(fund.id) == 32
    assert int(fund.id, 16) >= 0
    assert "btat" not in fund.id.lower()
    assert fund.retired_at is None


async def test_two_funds_cannot_wear_one_name(db_session: AsyncSession, fund: RRFund) -> None:
    """The id is never shown, so the name is the only identity on the screen that assigns
    money — and two funds sharing it there is a wrong transfer waiting to happen."""
    with pytest.raises(ConflictError):
        await create_fund(db_session, name="Shema Línguas")


async def test_a_retired_fund_keeps_its_name_against_a_new_one(
    db_session: AsyncSession, fund: RRFund
) -> None:
    """The uniqueness spans retired rows because the name still appears in the ledger's
    history, and a second fund wearing it would make one history read as two."""
    await retire_fund(db_session, fund_id="linguas")

    with pytest.raises(ConflictError):
        await create_fund(db_session, name="Shema Línguas")


async def test_a_nameless_fund_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(ValidationError):
        await create_fund(db_session, name="   ")


async def test_a_new_fund_is_born_at_three_zeros(db_session: AsyncSession) -> None:
    """GATE-01 D6 has funds born empty and the Gestores filling them (BE-09)."""
    fund = await create_fund(db_session, name="Tripod")

    balance = next(b for b in await fund_balances(db_session) if b.id == fund.id)
    assert (balance.allocated, balance.committed, balance.available) == (0, 0, 0)


# ——— renaming ————————————————————————————————————————————————————————————————————


async def test_renaming_moves_the_name_and_nothing_else(
    db_session: AsyncSession, fund: RRFund, author
) -> None:
    """DoD: the id does not move and no ``fund_id`` is patched anywhere.

    The request and the movement below are what make the second half checkable: both cite
    the fund by id, and a rename that touched it would orphan them.
    """
    await a_request(db_session, author, id="r1", stage=RRStage.APROVADO, fund_id="linguas")
    db_session.add(
        RRFundMovement(
            id="m1",
            fund_id="linguas",
            kind=RRMovementKind.ALLOCATION,
            amount=1,
            created_by=author.id,
        )
    )
    await db_session.commit()

    renamed = await rename_fund(db_session, fund_id="linguas", name="Shema Línguas e Culturas")

    assert renamed.id == "linguas"
    assert renamed.name == "Shema Línguas e Culturas"
    assert (await db_session.execute(select(RRRequest.fund_id))).scalars().all() == ["linguas"]
    assert (await db_session.execute(select(RRFundMovement.fund_id))).scalars().all() == ["linguas"]


async def test_renaming_to_a_name_another_fund_has_is_refused(
    db_session: AsyncSession, fund: RRFund
) -> None:
    other = await create_fund(db_session, name="Ora-Bridge")

    with pytest.raises(ConflictError):
        await rename_fund(db_session, fund_id=other.id, name="Shema Línguas")


async def test_renaming_a_fund_to_the_name_it_has_is_not_a_duplicate_of_itself(
    db_session: AsyncSession, fund: RRFund
) -> None:
    renamed = await rename_fund(db_session, fund_id="linguas", name="Shema Línguas")
    assert renamed.name == "Shema Línguas"


async def test_renaming_a_fund_that_does_not_exist_is_a_404(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await rename_fund(db_session, fund_id="nao-existe", name="Qualquer")


# ——— retiring ————————————————————————————————————————————————————————————————————


async def test_retiring_never_deletes_and_the_ledger_still_reads(
    db_session: AsyncSession, fund: RRFund, author
) -> None:
    """DoD: out of the list of choice, still in every line of the razão."""
    db_session.add(
        RRFundMovement(
            id="m1",
            fund_id="linguas",
            kind=RRMovementKind.ALLOCATION,
            amount=1000,
            created_by=author.id,
        )
    )
    await db_session.commit()

    retired = await retire_fund(db_session, fund_id="linguas")

    assert retired.retired_at is not None
    assert (await db_session.execute(select(RRFund.id))).scalars().all() == ["linguas"]
    assert (await db_session.execute(select(RRFundMovement.fund_id))).scalars().all() == ["linguas"]


async def test_a_retired_fund_is_still_listed_with_its_money(
    db_session: AsyncSession, fund: RRFund
) -> None:
    """Filtering it out of the read would erase from the Painel money the ledger holds.
    The list of choice is this list filtered on ``retired`` — never this list shortened."""
    await retire_fund(db_session, fund_id="linguas")

    balances = await fund_balances(db_session)
    assert [(b.id, b.retired) for b in balances] == [("linguas", True)]


@pytest.mark.parametrize("stage", [RRStage.TRIAGEM, RRStage.ANALISE])
async def test_retiring_under_an_undecided_request_is_refused_with_the_count(
    db_session: AsyncSession, fund: RRFund, author, stage: RRStage
) -> None:
    """DoD: 409, with the count in the response.

    The count travels because the Gestor's next move depends on it: one card is a card to
    re-point, eleven is a decision to postpone.
    """
    await a_request(db_session, author, id="r1", stage=stage, fund_id="linguas")
    await a_request(db_session, author, id="r2", stage=stage, fund_id="linguas")

    with pytest.raises(ConflictError) as refusal:
        await retire_fund(db_session, fund_id="linguas")

    assert "2" in str(refusal.value)
    await db_session.rollback()
    still = (await db_session.execute(select(RRFund.retired_at))).scalar_one()
    assert still is None


@pytest.mark.parametrize(
    "stage", [RRStage.APROVADO, RRStage.CONDICIONAL, RRStage.REVISAR, RRStage.RECUSADO]
)
async def test_a_decided_request_does_not_hold_a_fund_open(
    db_session: AsyncSession, fund: RRFund, author, stage: RRStage
) -> None:
    """Its money is either committed in the ledger, which retirement does not touch, or it
    is never coming — and neither is a reason to keep a fund open."""
    await a_request(db_session, author, id="r1", stage=stage, fund_id="linguas")

    retired = await retire_fund(db_session, fund_id="linguas")
    assert retired.retired_at is not None


async def test_retiring_twice_does_not_move_the_date(
    db_session: AsyncSession, fund: RRFund
) -> None:
    """An end stated twice is the same end; re-stamping would move the date of something
    that happened earlier, which is the one thing this column must not do."""
    first = await retire_fund(db_session, fund_id="linguas")
    stamped = first.retired_at

    again = await retire_fund(db_session, fund_id="linguas")
    assert again.retired_at == stamped


async def test_retiring_a_fund_that_does_not_exist_is_a_404(db_session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await retire_fund(db_session, fund_id="nao-existe")


# ——— the four reserved names —————————————————————————————————————————————————————


async def test_the_four_undecided_names_are_a_register_and_not_rows(
    db_session: AsyncSession, fund: RRFund
) -> None:
    """DoD: *lista à espera do Gestor*, never a seed.

    A fund row is an assertion about someone's money, and that is exactly the assertion
    GATE-01 says the client declined to make about these four.
    """
    assert RESERVED_FUND_NAMES == ("Shema BTAT", "Tripod", "OBT-Lab", "Ora-Bridge")

    rows = (await db_session.execute(select(RRFund.name))).scalars().all()
    assert set(rows).isdisjoint(RESERVED_FUND_NAMES)


# ——— the wire, and the one capability that opens it ——————————————————————————————


async def test_the_gestor_creates_renames_and_retires(db_session, client, rrf_app) -> None:
    """DoD 1: one capability, ``administer_funds``, held by the Gestor."""
    _user, headers = await as_role(db_session, rrf_app, "gestor", "gestor@fixture.test")

    created = await client.post(FUNDS, json={"name": "Tripod"}, headers=headers)
    assert created.status_code == 201
    fund_id = created.json()["id"]
    assert created.json()["retired_at"] is None

    renamed = await client.patch(
        f"{FUNDS}/{fund_id}", json={"name": "Tripod Brasil"}, headers=headers
    )
    assert renamed.status_code == 200
    assert renamed.json() == {"id": fund_id, "name": "Tripod Brasil", "retired_at": None}

    retired = await client.post(f"{FUNDS}/{fund_id}/retirement", headers=headers)
    assert retired.status_code == 200
    assert retired.json()["retired_at"] is not None


@pytest.mark.parametrize("role_key", ["equipe", "mesa", "lider"])
async def test_nobody_else_administers_a_fund(db_session, client, rrf_app, role_key: str) -> None:
    """The mesa included: ``manage_funds`` is the Painel's door and the mesa holds it, which
    is why the administration hangs off a capability of control instead."""
    _user, headers = await as_role(db_session, rrf_app, role_key, f"{role_key}@fixture.test")

    assert (await client.post(FUNDS, json={"name": "Tripod"}, headers=headers)).status_code == 403
    assert (
        await client.patch(f"{FUNDS}/linguas", json={"name": "Outro"}, headers=headers)
    ).status_code == 403
    assert (await client.post(f"{FUNDS}/linguas/retirement", headers=headers)).status_code == 403
    assert (await client.get(f"{FUNDS}/reserved-names", headers=headers)).status_code == 403


async def test_the_retirement_refusal_reaches_the_wire_as_409(
    db_session, client, rrf_app, fund, author
) -> None:
    await a_request(db_session, author, id="r1", stage=RRStage.TRIAGEM, fund_id="linguas")
    _user, headers = await as_role(db_session, rrf_app, "gestor", "gestor@fixture.test")

    refused = await client.post(f"{FUNDS}/linguas/retirement", headers=headers)

    assert refused.status_code == 409
    assert "1" in refused.text


async def test_an_id_on_the_wire_is_refused_rather_than_ignored(
    db_session, client, rrf_app
) -> None:
    """``extra="forbid"`` is what makes *the id is never the client's* audible."""
    _user, headers = await as_role(db_session, rrf_app, "gestor", "gestor@fixture.test")

    answered = await client.post(
        FUNDS, json={"id": "escolhido-por-mim", "name": "Tripod"}, headers=headers
    )
    assert answered.status_code == 422


async def test_the_reserved_names_are_offered_to_the_gestor(db_session, client, rrf_app) -> None:
    _user, headers = await as_role(db_session, rrf_app, "gestor", "gestor@fixture.test")

    offered = await client.get(f"{FUNDS}/reserved-names", headers=headers)

    assert offered.status_code == 200
    assert offered.json() == list(RESERVED_FUND_NAMES)


async def test_the_panel_read_carries_the_retirement_flag(
    db_session, client, rrf_app, fund
) -> None:
    """The mesa reads the Painel, so it reads a retired fund's money too — with the flag
    that tells the list of choice to drop it."""
    _user, headers = await as_role(db_session, rrf_app, "mesa", "mesa@fixture.test")

    listed = (await client.get(FUNDS, headers=headers)).json()
    assert [(f["id"], f["retired"]) for f in listed] == [("linguas", False)]

    await retire_fund(db_session, fund_id="linguas")

    listed = (await client.get(FUNDS, headers=headers)).json()
    assert [(f["id"], f["retired"]) for f in listed] == [("linguas", True)]
