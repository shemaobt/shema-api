"""Seed the resource-request module with the prototype's sample funds and board cards.

**The snapshot document comes from the module's own serializer** (BE-04, OBT-453), not
from a shape built here. It used to be built here, and that was the second serializer
``docs/resource_requests.md`` §4.2 forbids by name — a fixture whose snapshots are shaped
differently from production's is exactly what sends the next reader down the wrong path,
and this one had already drifted: it carried five of the spine's values and the real one
carries all of them.

Idempotent by design, like ``seed_apps_roles.py``: every row is looked up by a
deterministic id before it is written. That matters more here than anywhere else in this
repository, because ``rr_fund_movements`` is append-only — a second run that appended
instead of skipping would double every balance and there is no UPDATE to undo it with.

The data is the frontend's, at ``shemaobt/resource-request-form`` commit ``c56937c`` —
``src/fixtures/panel.ts`` for the ten board cards, ``src/constants/criteria.ts`` for the
criteria. **The funds are the exception, and they moved after that commit**: GATE-01
(OBT-447, 26/aug/2026) is the authority for the list and for which card draws from what,
and the frontend applies that same answer in its own ``funds.ts`` and ``panel.ts``.
Nothing here is real money or a real person — the fixture's ``solicitante`` names are
invented there, deliberately, because a request carries personal data.

Four things the fixture does not carry and this script decides, each named so nobody
reads them as ported:

* **The request type.** The board fixture has no type field. Each card takes the type its
  own subject states, and every card that comes out ``traducao`` names a Tipo 1 category
  outright — *NT*, *Tradução oral/áudio*, *Pesquisa sociolinguística*, *Porções* and
  *Audiovisual (ex.: JESUS Film)*, five of the nine in ``projectCategory``. The remaining
  five are read the same way from their own subject: a capacitação, a mentoria and the two
  Ready Vessels are ``treinamento``, the gravação is ``equipamentos``. The fund is
  deliberately **not** used to derive any of it, and since GATE-01 it could not be even
  if someone wanted to: seven cards draw from the one fund and three draw from none, so
  the field carries no signal about a type at all. The two *Ready Vessels* cards keep
  their names — Ready Vessels stopped being a fund, not a project.
* **The six scores behind each total.** The fixture carries a ``/30`` total and the
  schema stores per-criterion rows, because the total is derived and never stored. The
  six values are spread evenly over the total by ``_spread`` — sample data, not a mesa's
  judgement.
* **The eighteen criterion slugs came from here and no longer live here.** They were
  minted in this file because §9's vendored emission did not exist yet, with the promise
  that the emission would carry exactly these and the list would go away. BE-05 (OBT-454)
  landed the emission carrying them letter for letter, so ``CRITERION_KEYS`` is now read
  from ``app.utils.resource_request_vocabularies``. The prefix by request type survives
  and is not decoration: *Vínculo com um projeto de tradução ativo* is criterion 2 of both
  ``treinamento`` and ``equipamentos``, so an unprefixed slug would collide.
* **The two approval deductions.** *Comprometido* is a sum over the ledger, so the two
  cards sitting on ``aprovado`` need the movement that put them there; without it the
  board and the fund cards would disagree about the same money.

**Three of the ten carry no fund, and that is a state rather than a gap.** GATE-01
answered that the mesa assigns the fund at triage, so a request in ``triagem``
legitimately has none — and the three that carry none are exactly the three sitting in
that column. It is what ``rr_requests.fund_id`` is nullable for, and this is where the
column is first written both ways.

And two chips it drops rather than invents, on the five cards that are not ``traducao``.
The card's **povo** has no key in the form for ``treinamento`` and ``equipamentos`` at all
— A2 is rendered by ``traducao`` alone — so all five drop it. Its **língua** reaches those
two types only through A1-slim's table of language names, which ``—`` and ``Multi`` are
not, so four of the five drop that too and only the Ticuna card keeps one. Writing either
would say a section was asked when it never was, which is the distinction the sections
document exists to keep, and it is the same finding the contract's §6.2 already records
about the card's fund: the board card projects more than the form collects.
"""

import asyncio
import os
import sys
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.db.models.auth import User
from app.db.models.resource_request import (
    RREvaluation,
    RREvaluationScore,
    RRFund,
    RRFundMovement,
    RRMovementKind,
    RRRequest,
    RRRequestSections,
    RRRequestType,
    RRSnapshot,
    RRStage,
)
from app.services.resource_request._document import document
from app.utils.resource_request_vocabularies import CRITERION_KEYS

#: The fund the ten cards hang from. **This script no longer writes it** — BE-10
#: (OBT-471) moved the row to ``20260830_rr07``, because a fund line stopped being seed
#: data the day the Gestor started typing them: what the migration writes is the one name
#: GATE-01 confirmed, and everything after it is created through the API.
#:
#: The id stays ``linguas`` and is the one readable fund id in the product — the vendored
#: emission carries it and every card below writes it, so minting a uuid for this row
#: would make three places disagree. Every other id is opaque (``uuid4().hex``).
#:
#: **It is born with allocated 0, and the seed writes no ALLOCATION** (BE-07, OBT-456).
#: GATE-01 D6 has funds born empty and the Gestores filling them, so the prototype's
#: 480.000 is the frontend's dev fixture (``FUND_ALLOCATIONS`` in ``panel.ts``) and
#: never a seed value. An earlier version seeded it anyway, priced against the panel's
#: look — the two approved cards deduct 159.000, so an empty fund opens the panel at
#: **-159.000** — and that price is now paid knowingly: a negative *disponível* is the
#: warning state GATE-01 D5 chose over a refusal, and it says the true thing, that money
#: was promised which nobody has put in. The first Gestor allocation (BE-09, OBT-469) is
#: what fills it.
CONFIRMED_FUND_ID = "linguas"

LANGUAGE_PLACEHOLDERS = {"—", "Multi"}


@dataclass(frozen=True)
class SeedCard:
    """One board card, ported field for field from ``PANEL_REQUESTS``."""

    n: int
    request_type: RRRequestType
    name: str
    solicitante: str
    lang: str
    people: str
    fund: str | None
    valor: Decimal
    stage: RRStage
    score: int | None = field(default=None)


SEED_CARDS = [
    SeedCard(
        n=1,
        request_type=RRRequestType.TRADUCAO,
        name="Tradução do NT — Matsés",
        solicitante="Ana Beatriz Nogueira",
        lang="Matsés",
        people="Matsés",
        fund="linguas",
        valor=Decimal("128000"),
        score=26,
        stage=RRStage.APROVADO,
    ),
    SeedCard(
        n=2,
        request_type=RRRequestType.TRADUCAO,
        name="Áudio-Bíblia Paiter Suruí",
        solicitante="Rafael Mendonça",
        lang="Suruí",
        people="Paiter Suruí",
        fund="linguas",
        valor=Decimal("74000"),
        score=22,
        stage=RRStage.ANALISE,
    ),
    SeedCard(
        n=3,
        request_type=RRRequestType.TREINAMENTO,
        name="Capacitação de tradutores — Norte",
        solicitante="Juliana Prado",
        lang="—",
        people="Equipes JOCUM",
        fund=None,
        valor=Decimal("38000"),
        stage=RRStage.TRIAGEM,
    ),
    SeedCard(
        n=4,
        request_type=RRRequestType.TREINAMENTO,
        name="Ready Vessels — Acre",
        solicitante="Thiago Barcelos",
        lang="Multi",
        people="Jovens jocumeiros",
        fund="linguas",
        valor=Decimal("26000"),
        score=19,
        stage=RRStage.CONDICIONAL,
    ),
    SeedCard(
        n=5,
        request_type=RRRequestType.TRADUCAO,
        name="Pesquisa sociolinguística Yanomami",
        solicitante="Marina Vasconcelos",
        lang="Yanomami",
        people="Yanomami",
        fund="linguas",
        valor=Decimal("31000"),
        score=24,
        stage=RRStage.APROVADO,
    ),
    SeedCard(
        n=6,
        request_type=RRRequestType.EQUIPAMENTOS,
        name="Equipamento de gravação Ticuna",
        solicitante="Caio Ferreira",
        lang="Ticuna",
        people="Ticuna",
        fund=None,
        valor=Decimal("18000"),
        stage=RRStage.TRIAGEM,
    ),
    SeedCard(
        n=7,
        request_type=RRRequestType.TRADUCAO,
        name="Porções das Escrituras Kayapó",
        solicitante="Letícia Amorim",
        lang="Kayapó",
        people="Mebêngôkre",
        fund="linguas",
        valor=Decimal("52000"),
        score=14,
        stage=RRStage.REVISAR,
    ),
    SeedCard(
        n=8,
        request_type=RRRequestType.TRADUCAO,
        name="JESUS Film — Guajajara",
        solicitante="Douglas Rocha",
        lang="Guajajara",
        people="Tenetehara",
        fund="linguas",
        valor=Decimal("96000"),
        score=11,
        stage=RRStage.RECUSADO,
    ),
    SeedCard(
        n=9,
        request_type=RRRequestType.TREINAMENTO,
        name="Mentoria de tradutores",
        solicitante="Priscila Tavares",
        lang="—",
        people="Rede Shemá",
        fund="linguas",
        valor=Decimal("22000"),
        score=21,
        stage=RRStage.ANALISE,
    ),
    SeedCard(
        n=10,
        request_type=RRRequestType.TREINAMENTO,
        name="Ready Vessels — Roraima",
        solicitante="Eduardo Lins",
        lang="Multi",
        people="Jovens jocumeiros",
        fund=None,
        valor=Decimal("29000"),
        stage=RRStage.TRIAGEM,
    ),
]


def _spread(total: int, criteria: int = 6, ceiling: int = 5) -> list[int]:
    """Split a ``/30`` total into per-criterion scores, as evenly as it divides.

    Every value lands inside the 0-5 the schema checks, because a total of at most
    ``criteria * ceiling`` cannot force one above it.
    """
    if total > criteria * ceiling:
        raise ValueError(f"{total} does not fit in {criteria} criteria of at most {ceiling}")
    base, remainder = divmod(total, criteria)
    return [base + 1] * remainder + [base] * (criteria - remainder)


def _sections(card: SeedCard) -> dict[str, Any]:
    """The card's chips, in the section keys the request's type actually renders."""
    fields: dict[str, str] = {}
    langs: list[dict[str, str]] = []

    if card.request_type is RRRequestType.TRADUCAO:
        fields["lang_name"] = card.lang
        fields["people_name"] = card.people
    elif card.lang not in LANGUAGE_PLACEHOLDERS:
        langs.append({"name": card.lang, "code": ""})

    return {"fields": fields, "langs": langs, "team": [], "chrono": [], "checks": {}}


async def _author(db: AsyncSession, email: str) -> User:
    """Resolve the account every seeded row is written by, or refuse to seed.

    ``rr_requests.created_by`` and ``rr_fund_movements.created_by`` stopped being nullable
    when GATE-02's D1 answered accounts, so the fixture needs an author the way a real
    request does. It is **looked up and never created**, the shape ``seed_project.py``
    already uses: inventing a person to satisfy a column would put a fabricated human in
    ``users``, and the sample data is invented precisely so that no real one is.

    Refusing is the honest failure. A seed that silently attached ten requests to whichever
    account happened to be first would be sample data making a claim about a real person.
    """
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        raise SystemExit(
            f"Nenhuma conta com o e-mail {email!r}. O seed grava o autor de cada pedido e de "
            "cada movimento, e não inventa um: crie a conta antes (scripts/grant_app_role.py) "
            "ou passe outro e-mail."
        )
    return user


async def _require_confirmed_fund(db: AsyncSession) -> None:
    """Check that the migration's fund row is there — and never write it (BE-10, OBT-471).

    Seven of the ten cards name this fund, so the script cannot run without it; but it is
    no longer this script's row to create. ``20260830_rr07`` writes it, every fund after it
    is created by the Gestor through the API, and a seed that wrote one anyway would be
    the fixture inventing a fund — the same claim about someone's money the four undecided
    names are careful not to make.

    Refusing loudly is the ``_author`` shape: the alternative is an ``IntegrityError`` from
    the seventh card's foreign key, which names a constraint to somebody who forgot to
    migrate.
    """
    fund = (
        await db.execute(select(RRFund).where(RRFund.id == CONFIRMED_FUND_ID))
    ).scalar_one_or_none()
    if fund is None:
        raise SystemExit(
            f"O fundo {CONFIRMED_FUND_ID!r} não existe. Ele é escrito pela migration "
            "20260830_rr07, não por este seed: rode `uv run alembic upgrade head` antes."
        )


async def _seed_card(db: AsyncSession, card: SeedCard, author: User) -> None:
    request_id = f"rr-seed-request-{card.n}"
    request = (
        await db.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request:
        return

    row = RRRequest(
        id=request_id,
        request_type=card.request_type,
        reg_name=card.name,
        stage=card.stage,
        fund_id=card.fund,
        amount_requested=card.valor,
        tpp_name=card.solicitante,
        created_by=author.id,
    )
    db.add(row)
    await db.flush()

    sections = RRRequestSections(request_id=request_id, content=_sections(card))
    db.add(sections)
    await db.flush()

    if card.stage is RRStage.APROVADO:
        db.add(
            RRFundMovement(
                id=f"rr-seed-approval-{card.n}",
                fund_id=card.fund,
                request_id=request_id,
                kind=RRMovementKind.APPROVAL_DEDUCTION,
                amount=card.valor,
                reason="Aprovação de exemplo do protótipo",
                created_by=author.id,
            )
        )

    if card.score is None:
        return

    snapshot_id = f"rr-seed-snapshot-{card.n}"
    db.add(RRSnapshot(id=snapshot_id, request_id=request_id, document=document(row, sections, [])))
    await db.flush()

    evaluation_id = str(uuid.uuid4())
    db.add(RREvaluation(id=evaluation_id, snapshot_id=snapshot_id))
    await db.flush()

    for criterion_key, score in zip(
        CRITERION_KEYS[card.request_type], _spread(card.score), strict=True
    ):
        db.add(
            RREvaluationScore(evaluation_id=evaluation_id, criterion_key=criterion_key, score=score)
        )


#: The account every seeded row is written by. An argument first, then the environment —
#: there is deliberately no default, because a default would be a real e-mail address
#: hard-coded in a repository, or a fake one that resolves to nobody and fails later than
#: it should.
AUTHOR_ENV = "RR_SEED_AUTHOR"


async def seed(author_email: str) -> None:
    """Write the ten sample board cards against the fund the migration already wrote.

    No evaluation carries a decision. The board column a card sits in does not imply one
    — the mesa moves cards without evaluating them — and inverting that mapping is
    exactly the drift FE-22's contract §2.3 exists to prevent.

    Nothing here writes an attendee list or a history row, and that is not an omission:
    ``rr_evaluation_attendees`` is who was in the room and ``rr_*_field_history`` is who
    changed what, and the seed never held a meeting and never edited anything. Inventing
    either would be the fabricated data this fixture is careful not to be.
    """
    async with AsyncSessionLocal() as db:
        author = await _author(db, author_email)
        await _require_confirmed_fund(db)
        for card in SEED_CARDS:
            await _seed_card(db, card, author)
        await db.commit()


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(AUTHOR_ENV)
    if not email:
        raise SystemExit(
            f"uso: python -m scripts.seed_resource_requests <e-mail do autor>  "
            f"(ou defina {AUTHOR_ENV})"
        )
    asyncio.run(seed(email))
