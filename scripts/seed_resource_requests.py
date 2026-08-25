"""Seed the resource-request module with the prototype's sample funds and board cards.

Idempotent by design, like ``seed_apps_roles.py``: every row is looked up by a
deterministic id before it is written. That matters more here than anywhere else in this
repository, because ``rr_fund_movements`` is append-only — a second run that appended
instead of skipping would double every balance and there is no UPDATE to undo it with.

The data is the frontend's, at ``shemaobt/resource-request-form`` commit ``c56937c``:
``src/constants/funds.ts`` for the five funds, ``src/fixtures/panel.ts`` for the
allocations and the ten board cards, ``src/constants/criteria.ts`` for the criteria.
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
  deliberately **not** used to derive any of it: the old↔new fund correspondence is
  exactly what GATE-01 is still deciding.
* **The six scores behind each total.** The fixture carries a ``/30`` total and the
  schema stores per-criterion rows, because the total is derived and never stored. The
  six values are spread evenly over the total by ``_spread`` — sample data, not a mesa's
  judgement.
* **The eighteen criterion slugs.** ``docs/resource_requests.md`` §4.3 requires a key and
  forbids an index, and the vendored vocabulary emission of §9 does not exist yet. They
  are minted here, mechanically from the Portuguese labels and prefixed by request type —
  the prefix is not decoration: *Vínculo com um projeto de tradução ativo* is criterion 2
  of both ``treinamento`` and ``equipamentos``, so an unprefixed slug would collide. When
  §9's emission lands it must carry exactly these, and this list goes away.
* **The two approval deductions.** *Comprometido* is a sum over the ledger, so the two
  cards sitting on ``aprovado`` need the movement that put them there; without it the
  board and the fund cards would disagree about the same money.

And two chips it drops rather than invents. The card's **povo** has no key in the form
for ``treinamento`` and ``equipamentos`` — A2 is rendered by ``traducao`` alone — and its
**língua** reaches those two types only through A1-slim's table of language names, which
``—`` and ``Multi`` are not. So four of the ten cards store neither. Writing them would
say a section was asked when it never was, which is the distinction the sections document
exists to keep, and it is the same finding the contract's §6.2 already records about the
card's fund: the board card projects more than the form collects.
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
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

SEED_FUNDS = [
    ("linguas", "Shema Línguas", Decimal("480000")),
    ("treinamentos", "Shema BTAT", Decimal("150000")),
    ("ready", "Shema Tripod", Decimal("90000")),
    ("equip", "Shema OBT-Lab", Decimal("120000")),
    ("pesquisa", "Shema Ora-Bridge", Decimal("60000")),
]

CRITERION_KEYS: dict[RRRequestType, list[str]] = {
    RRRequestType.TRADUCAO: [
        "traducao_necessidade_urgencia",
        "traducao_receptividade_demanda",
        "traducao_capacidade_equipe",
        "traducao_viabilidade_cronograma",
        "traducao_orcamento",
        "traducao_alinhamento_eten",
    ],
    RRRequestType.TREINAMENTO: [
        "treinamento_lacuna_capacitacao",
        "treinamento_vinculo_projeto",
        "treinamento_formato",
        "treinamento_capacidade_equipe",
        "treinamento_impacto",
        "treinamento_custo_beneficio",
    ],
    RRRequestType.EQUIPAMENTOS: [
        "equipamentos_necessidade",
        "equipamentos_vinculo_projeto",
        "equipamentos_adequacao_tecnica",
        "equipamentos_custo_beneficio",
        "equipamentos_manutencao",
        "equipamentos_orcamento",
    ],
}

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
    fund: str
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
        fund="treinamentos",
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
        fund="ready",
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
        fund="pesquisa",
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
        fund="equip",
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
        fund="treinamentos",
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
        fund="ready",
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


def _snapshot_document(card: SeedCard) -> dict[str, Any]:
    """What submission freezes: the spine as submitted, the sections, the budget lines."""
    return {
        "request": {
            "request_type": card.request_type.value,
            "reg_name": card.name,
            "currency": "BRL",
            "amount_requested": str(card.valor),
            "tpp_name": card.solicitante,
        },
        "sections": _sections(card),
        "budget": [],
    }


async def _seed_funds(db: AsyncSession) -> None:
    for fund_id, name, allocated in SEED_FUNDS:
        fund = (await db.execute(select(RRFund).where(RRFund.id == fund_id))).scalar_one_or_none()
        if not fund:
            db.add(RRFund(id=fund_id, name=name, provisional=True))
            await db.flush()

        movement_id = f"rr-seed-allocation-{fund_id}"
        existing = (
            await db.execute(select(RRFundMovement).where(RRFundMovement.id == movement_id))
        ).scalar_one_or_none()
        if not existing:
            db.add(
                RRFundMovement(
                    id=movement_id,
                    fund_id=fund_id,
                    kind=RRMovementKind.ALLOCATION,
                    amount=allocated,
                    reason="Alocação de exemplo do protótipo",
                )
            )


async def _seed_card(db: AsyncSession, card: SeedCard) -> None:
    request_id = f"rr-seed-request-{card.n}"
    request = (
        await db.execute(select(RRRequest).where(RRRequest.id == request_id))
    ).scalar_one_or_none()
    if request:
        return

    db.add(
        RRRequest(
            id=request_id,
            request_type=card.request_type,
            reg_name=card.name,
            stage=card.stage,
            fund_id=card.fund,
            amount_requested=card.valor,
            tpp_name=card.solicitante,
        )
    )
    await db.flush()

    db.add(RRRequestSections(request_id=request_id, content=_sections(card)))
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
            )
        )

    if card.score is None:
        return

    snapshot_id = f"rr-seed-snapshot-{card.n}"
    db.add(RRSnapshot(id=snapshot_id, request_id=request_id, document=_snapshot_document(card)))
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


async def seed() -> None:
    """Write the five funds, their allocations and the ten sample board cards.

    No evaluation carries a decision. The board column a card sits in does not imply one
    — the mesa moves cards without evaluating them — and inverting that mapping is
    exactly the drift FE-22's contract §2.3 exists to prevent.
    """
    async with AsyncSessionLocal() as db:
        await _seed_funds(db)
        for card in SEED_CARDS:
            await _seed_card(db, card)
        await db.commit()


if __name__ == "__main__":
    asyncio.run(seed())
