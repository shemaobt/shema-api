"""The batch ``network`` consent — the script that waits for the client's basis.

Karina answered on 22/sep that everybody in the network authorized being held, and the basis
has not arrived. What these tests hold is that the script is safe to run the day it does: the
basis is an argument checked by the API's own rule, a second run writes nothing, a consent
that stands keeps its own answer, the operator is an account, nothing prints a person — and
nothing in the application, the migrations or CI runs it.

The people are inserted straight into the table on purpose. Through the API nobody can lack
``network`` — ``add_intercessor`` refuses them — and those rows are the script's whole use:
a network imported from wherever the client keeps it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.shema_consent import ShemaConsentContext, ShemaIntercessorConsent
from app.db.models.shema_intercessor import ShemaIntercessor
from scripts.shema_backfill_network_consent import (
    UnknownOperator,
    backfill,
    checked_basis,
    main,
    report,
)
from tests.baker import make_user

ROOT = Path(__file__).resolve().parents[2]
BASIS = "autorização verbal, encontro regional de 2025 — lista confirmada pela coordenação"
OPERATOR = "karina.operator@shema.test"


async def _person(db_session, name: str, contact: str) -> str:
    person = ShemaIntercessor(name=name, country="BR", contact=contact)
    db_session.add(person)
    await db_session.commit()
    return person.id


async def _network_rows(db_session) -> dict[str, ShemaIntercessorConsent]:
    rows = await db_session.execute(
        select(ShemaIntercessorConsent).where(
            ShemaIntercessorConsent.context == ShemaConsentContext.NETWORK
        )
    )
    return {row.intercessor_id: row for row in rows.scalars()}


@pytest.fixture()
async def network(db_session):
    """Two people nobody recorded a consent for, and one who answered on their own."""
    operator = await make_user(db_session, email=OPERATOR)
    other = await make_user(db_session, email="circle.member@shema.test")
    bare = [
        await _person(db_session, "Pessoa Sem Registro", "sem.registro@example.org"),
        await _person(db_session, "Outra Sem Registro", "+55 11 90000-0001"),
    ]
    answered = await _person(db_session, "Quem Respondeu", "respondeu@example.org")
    long_ago = datetime.now(UTC) - timedelta(days=200)
    db_session.add(
        ShemaIntercessorConsent(
            intercessor_id=answered,
            context=ShemaConsentContext.NETWORK,
            basis="resposta própria por WhatsApp",
            recorded_by=other.id,
            recorded_at=long_ago,
        )
    )
    await db_session.commit()
    return {"operator": operator, "bare": bare, "answered": answered, "long_ago": long_ago}


async def test_the_backfill_records_network_only_for_who_lacks_it_and_a_second_run_changes_nothing(
    db_session, network
) -> None:
    """**The DoD's third line.** The first run writes the two missing rows on the stated basis,
    naming who ran it; the second finds nobody; the person who answered on their own keeps
    their basis, their recorder and their date — a batch never overwrites an answer."""
    first = await backfill(db_session, basis=BASIS, recorded_by_email=OPERATOR, write=True)
    second = await backfill(db_session, basis=BASIS, recorded_by_email=OPERATOR, write=True)

    assert (first.lacking, first.recorded) == (2, 2)
    assert (second.lacking, second.recorded) == (0, 0)
    rows = await _network_rows(db_session)
    assert set(rows) == {*network["bare"], network["answered"]}
    for person_id in network["bare"]:
        assert rows[person_id].basis == BASIS
        assert rows[person_id].recorded_by == network["operator"].id
    kept = rows[network["answered"]]
    assert kept.basis == "resposta própria por WhatsApp"
    assert kept.recorded_by != network["operator"].id
    assert abs(kept.recorded_at - network["long_ago"]) < timedelta(seconds=1)


async def test_a_dry_run_writes_nothing(db_session, network) -> None:
    outcome = await backfill(db_session, basis=BASIS, recorded_by_email=OPERATOR, write=False)

    assert (outcome.lacking, outcome.recorded) == (2, 0)
    assert set(await _network_rows(db_session)) == {network["answered"]}


async def test_the_operator_must_be_an_account(db_session, network) -> None:
    """``recorded_by`` is a foreign key and the answer to *who stated this basis* — an address
    that is nobody stops the run before anything is written."""
    with pytest.raises(UnknownOperator):
        await backfill(db_session, basis=BASIS, recorded_by_email="nobody@shema.test", write=True)

    assert set(await _network_rows(db_session)) == {network["answered"]}


@pytest.mark.parametrize(
    "argv",
    [
        pytest.param(["--recorded-by", OPERATOR, "--apply"], id="no-basis"),
        pytest.param(["--recorded-by", OPERATOR, "--basis", "   ", "--apply"], id="blank-basis"),
        pytest.param(["--recorded-by", OPERATOR, "--basis", "x" * 301], id="basis-too-long"),
        pytest.param(["--basis", BASIS], id="no-operator"),
    ],
)
def test_the_basis_is_an_argument_and_a_blank_one_is_refused(argv: list[str]) -> None:
    """Refused by the argument parser, before any connection is opened: the basis is the
    evidence a consent row stands on, and the API's own rule (``ConsentGrant``) is the check."""
    with pytest.raises(SystemExit) as refused:
        main(argv)

    assert refused.value.code == 2


def test_the_basis_is_checked_by_the_rule_the_api_uses() -> None:
    assert checked_basis(f"  {BASIS}  ") == BASIS
    with pytest.raises(ValueError, match="basis"):
        checked_basis(" \t ")


async def test_the_backfill_prints_counts_and_never_a_person(db_session, network) -> None:
    dry = report(await backfill(db_session, basis=BASIS, recorded_by_email=OPERATOR, write=False))
    done = report(await backfill(db_session, basis=BASIS, recorded_by_email=OPERATOR, write=True))

    assert "2 person(s)" in dry and "Nothing was written" in dry
    assert "2 person(s)" in done
    for text in (dry, done):
        for secret in ("Sem Registro", "sem.registro@example.org", "90000", "BR", BASIS):
            assert secret not in text


def test_nothing_in_the_application_or_the_migrations_runs_it() -> None:
    """*Not executed in this issue*, held as a property: the script's name appears in no file
    the server, a migration, a deploy or CI runs."""
    callers = [
        str(path.relative_to(ROOT))
        for folder in ("app", "alembic", ".github")
        for path in sorted((ROOT / folder).rglob("*"))
        if path.is_file()
        and path.suffix in {".py", ".yml", ".yaml", ".sh", ".toml", ".cfg"}
        and "shema_backfill_network_consent" in path.read_text(encoding="utf-8")
    ]

    assert callers == []
