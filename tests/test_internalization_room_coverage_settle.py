import asyncio
import json
import logging
import re
import sys
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.models.internalization_room import CoverageFrame, CoverageView
from app.services.internalization_room import background
from app.services.internalization_room import sessions as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import absence_index, element_keys
from app.services.internalization_room.classify_coverage import _parse, classify_coverage
from app.services.internalization_room.comprehension.checkpoints import (
    checkpoints_for,
    scene_ids_for,
)
from app.services.internalization_room.comprehension.evidence import (
    EvidenceMethod,
    EvidenceObservation,
    EvidenceResult,
)
from app.services.internalization_room.comprehension.state import ComprehensionState
from app.services.internalization_room.coverage import CoverageStatus, initial_state
from app.services.internalization_room.coverage_channel import subscribe
from app.services.internalization_room.release import (
    InternalizationReleaseBlocked,
    build_internalization_release,
)

CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
P = "P03"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _fully_supported_comprehension(pericope: str) -> ComprehensionState:
    ledger = [
        EvidenceObservation(
            id=f"ev-{index}",
            unit_id=checkpoint.id,
            probe_id=f"probe-{index}",
            method=EvidenceMethod.MICRO_TELLBACK,
            result=EvidenceResult.DEMONSTRATED,
        )
        for index, checkpoint in enumerate(checkpoints_for(pericope))
    ]
    return ComprehensionState(
        ledger=ledger,
        practiced_scene_ids=scene_ids_for(pericope),
    )


def _whole_passage_engaged(pericope: str) -> str:
    return json.dumps(
        {
            "decisions": [
                {"element_id": key, "new_status": "engaged", "evidence": "a equipe trabalhou"}
                for key in element_keys(pericope)
            ]
        }
    )


def _whole_passage_partially_engaged(pericope: str) -> str:
    return json.dumps(
        {
            "decisions": [
                {
                    "element_id": key,
                    "new_status": "partially_engaged",
                    "evidence": "a equipe ecoou o Guia",
                }
                for key in element_keys(pericope)
            ]
        }
    )


@pytest.fixture
def patch_classifier(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.classify_coverage"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            agent.system = system_prompt
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


async def test_a_later_settle_does_not_darken_an_earned_bead(db_session: AsyncSession) -> None:
    session = await service.create_session(db_session, pericope=P)
    keys = element_keys(P)
    earned = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    earned[keys[0]] = CoverageStatus.ENGAGED.value
    await service.apply_coverage(db_session, session.id, earned)

    stale = dict.fromkeys(keys, CoverageStatus.NOT_ENCOUNTERED.value)
    stale[keys[1]] = CoverageStatus.SURFACED.value
    await service.apply_coverage(db_session, session.id, stale)

    assert session.coverage_state[keys[0]] == CoverageStatus.ENGAGED.value


def test_a_decision_lands_in_the_bucket_its_new_status_names(caplog) -> None:
    reply = json.dumps(
        {
            "decisions": [
                {"element_id": "scene:1", "new_status": "engaged", "evidence": "contaram a cena"},
                {"element_id": "scene:2", "new_status": "surfaced", "evidence": "o Guia citou"},
                {"element_id": "scene:3", "new_status": "partially_engaged", "evidence": "ecoaram"},
            ]
        }
    )

    with caplog.at_level(logging.WARNING):
        verdict = _parse(reply)

    assert verdict == {"surfaced": ["scene:2"], "engaged": ["scene:1"]}, (
        "o quarto estado era a casa do eco, e o piso descia até ela; a conta ecoada "
        "fica onde está e o status aposentado vira aviso no log"
    )
    assert "unusable decision" in caplog.text


async def test_a_settled_exchange_moves_the_bead_the_classifier_named(patch_classifier) -> None:
    keys = element_keys(P)
    patch_classifier(
        json.dumps(
            {
                "decisions": [
                    {"element_id": keys[0], "new_status": "engaged", "evidence": "contaram a cena"}
                ]
            }
        )
    )

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe contou a cena",
        guide_response="o Guia devolveu a pergunta",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    assert settled[keys[0]] == CoverageStatus.ENGAGED.value, (
        "a troca atravessava o classificador e voltava com o tracker intacto, "
        "então nenhuma conta do colar avançava"
    )


async def test_a_passage_settled_from_decisions_closes_the_session(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_engaged(P))
    session = await service.create_session(db_session, pericope=P)
    session = await service.save_comprehension(
        db_session, session, _fully_supported_comprehension(P)
    )

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe trabalhou a passagem inteira",
        guide_response="o Guia acompanhou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    assert session.status is IRSessionStatus.DONE, (
        "o classificador nunca movia uma conta, então o piso jamais era atingido "
        "e a passagem não tinha como terminar"
    )


async def test_a_settled_passage_drops_the_coverage_blocker_from_the_release(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_engaged(P))
    session = await service.create_session(db_session, pericope=P)

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe trabalhou a passagem inteira",
        guide_response="o Guia acompanhou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    blockers: list[str] = []
    try:
        await build_internalization_release(db_session, session)
    except InternalizationReleaseBlocked as blocked:
        blockers = blocked.blockers

    assert "coverage_floor_not_met" not in blockers, (
        "o colar ficava vazio por mais que a equipe trabalhasse, "
        "e a soltura respondia piso não atingido para sempre"
    )


async def test_a_classifier_still_answering_the_retired_status_moves_nothing(
    db_session: AsyncSession, patch_classifier
) -> None:
    """The word the model was taught for an echo no longer reaches the ledger.

    It used to be the one status the floor was lowered to accept: a whole passage of
    "sim" and "foi isso mesmo" closed the session. A model that still says it finds no
    bucket, and the passage stays open.
    """
    patch_classifier(_whole_passage_partially_engaged(P))
    session = await service.create_session(db_session, pericope=P)
    session = await service.save_comprehension(
        db_session, session, _fully_supported_comprehension(P)
    )

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe repetiu o que o Guia notou",
        guide_response="o Guia apontou o silêncio",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    assert session.coverage_state == initial_state(P), "uma decisão partially_engaged moveu conta"
    assert session.status is IRSessionStatus.IN_PROGRESS, (
        "a passagem inteira em 'sim' e 'foi isso mesmo' fechava a sessão"
    )


async def test_a_passage_the_team_only_echoed_keeps_the_coverage_blocker_on_the_release(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_partially_engaged(P))
    session = await service.create_session(db_session, pericope=P)

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe repetiu o que o Guia notou",
        guide_response="o Guia apontou o silêncio",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )
    session = await service.apply_coverage(db_session, session.id, settled)

    blockers: list[str] = []
    try:
        await build_internalization_release(db_session, session)
    except InternalizationReleaseBlocked as blocked:
        blockers = blocked.blockers

    assert "coverage_floor_not_met" in blockers, (
        "a soltura deixava de nomear a cobertura numa passagem que a equipe só ecoou"
    )


def test_a_reply_with_no_decisions_says_so_instead_of_reading_as_no_change(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        verdict = _parse(json.dumps({"retelling": {"scope": "S1", "approved": True}}))

    assert verdict == {"surfaced": [], "engaged": []}
    assert "no decisions list" in caplog.text, (
        "uma resposta sem o array voltava vazia calada, igualzinho a um turno "
        "em que nada mudou — foi esse silêncio que escondeu o bug por dois releases"
    )


def test_a_decision_carrying_an_unknown_status_is_named_in_the_log(caplog) -> None:
    reply = json.dumps({"decisions": [{"element_id": "scene:1", "new_status": "not_encountered"}]})

    with caplog.at_level(logging.WARNING):
        verdict = _parse(reply)

    assert verdict == {"surfaced": [], "engaged": []}
    assert "unusable decision" in caplog.text, (
        "um status que o parser não roteia sumia sem deixar rastro, "
        "e a conta parada parecia decisão do classificador"
    )


def test_a_reply_the_parser_cannot_read_buckets_nothing_instead_of_failing() -> None:
    unreadable = _parse("desculpa, não consegui classificar")
    not_an_object = _parse(json.dumps(["surfaced", "engaged"]))

    assert unreadable == not_an_object == {"surfaced": [], "engaged": []}


async def test_the_prompt_asks_for_the_shape_the_parser_reads(patch_classifier) -> None:
    agent = patch_classifier(_whole_passage_engaged(P))

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance="a equipe trabalhou a passagem inteira",
        guide_response="o Guia acompanhou",
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    missing = [
        name
        for name in (
            "decisions",
            "element_id",
            "new_status",
            "surfaced",
            "engaged",
        )
        if name not in agent.system
    ]

    assert missing == [], (
        "o parser lia chaves que o prompt nunca pediu, e nenhum teste olhava as duas "
        "pontas ao mesmo tempo, que é como a deriva atravessou dois releases"
    )


async def test_an_element_the_passage_does_not_hold_is_named_in_the_log(
    patch_classifier, caplog
) -> None:
    patch_classifier(
        json.dumps(
            {
                "decisions": [
                    {
                        "element_id": "being:NAO_EXISTE",
                        "new_status": "engaged",
                        "evidence": "o modelo inventou uma chave",
                    }
                ]
            }
        )
    )

    with caplog.at_level(logging.WARNING):
        settled = await classify_coverage(
            coverage_state=initial_state(P),
            team_utterance="a equipe falou",
            guide_response="o Guia respondeu",
            classifier_prompt=CLASSIFIER,
            pericope_num=P,
            settings=_settings(),
        )

    assert settled == initial_state(P)
    assert "does not hold" in caplog.text, (
        "o merge descartava a chave impossível de resolver em silêncio, e um classificador "
        "respondendo só em ids que a espinha não tem ficava idêntico a um que nada achou — "
        "foi por essa fresta que a mesma falha passou três vezes"
    )


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


async def _settle(session_id: str, turn_id: str) -> None:
    await background.settle_coverage(
        session_id=session_id,
        turn_id=turn_id,
        team_utterance="a equipe contou a cena",
        guide_response="o Guia devolveu a pergunta",
        pericope_num=P,
    )


async def test_a_settled_turn_reaches_every_subscriber_of_its_session_and_no_other(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    keys = element_keys(P)
    one_bead = initial_state(P)
    one_bead[keys[0]] = CoverageStatus.ENGAGED.value

    async def _classified(**_: Any) -> dict[str, str]:
        return one_bead

    monkeypatch.setattr(background, "classify_coverage", _classified)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)
    other = await service.create_session(db_session, pericope=P)

    async with (
        subscribe(session.id) as first,
        subscribe(session.id) as second,
        subscribe(other.id) as elsewhere,
    ):
        await _settle(session.id, "turn-7")

        announced = CoverageFrame(
            turn_id="turn-7",
            status="settled",
            coverage=CoverageView(
                engaged=1, surfaced=1, total=len(keys), absence_index=absence_index(P)
            ),
        )
        assert first.get_nowait() == second.get_nowait() == announced, (
            "o settle gravava a cobertura e ficava calado, e o app só a via "
            "adivinhando trinta segundos e perguntando uma vez"
        )
        assert elsewhere.empty(), "a cobertura de uma sessão chegava ao assinante de outra"


async def test_a_classifier_that_raises_announces_the_failure_instead_of_leaving_the_wait(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _broken(**_: Any) -> dict[str, str]:
        raise RuntimeError("o modelo caiu")

    monkeypatch.setattr(background, "classify_coverage", _broken)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    async with subscribe(session.id) as waiting:
        await _settle(session.id, "turn-8")

        assert waiting.get_nowait() == CoverageFrame(
            turn_id="turn-8", status="failed", coverage=None
        ), (
            "o except engolia a falha com um log, e o app esperava o timeout inteiro "
            "por um turno que nunca ia assentar"
        )


class _SlowClassifier:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        await asyncio.sleep(0.07)
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text='{"decisions": []}')],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


def _coverage_timing(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.getMessage() for r in caplog.records if "[coverage-timing]" in r.getMessage()]


async def test_a_settled_turn_says_how_long_the_classifier_took_and_how_many_tablets_heard(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.core.config import get_settings
    from app.services.internalization_room import llm

    classifier = _SlowClassifier()
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=classifier)
    )
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    with caplog.at_level(logging.INFO):
        async with subscribe(session.id), subscribe(session.id):
            await _settle(session.id, "turn-9")

    lines = _coverage_timing(caplog)
    assert len(lines) == 1, "o classificador das contas nunca tinha sido cronometrado"
    classifier_ms = re.search(r" classifier=(\d+)ms ", lines[0])
    assert classifier_ms is not None and int(classifier_ms.group(1)) >= 70
    assert f"session={session.id} " in lines[0]
    assert lines[0].endswith(" delivered=2"), "ninguém sabia se o aviso chegava ao tablet"


async def test_a_settle_that_fails_still_says_whether_the_failure_reached_a_tablet(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    async def _broken(**_: Any) -> dict[str, str]:
        raise RuntimeError("o modelo caiu")

    monkeypatch.setattr(background, "classify_coverage", _broken)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    with caplog.at_level(logging.INFO):
        await _settle(session.id, "turn-10")

    lines = _coverage_timing(caplog)
    assert len(lines) == 1
    assert lines[0].endswith(" delivered=0"), "o settle que falhava sumia do cronômetro"


@pytest.fixture
def connections_out() -> Iterator[list[int]]:
    from sqlalchemy import event

    from app.core.database import engine

    out = [0]

    def _checked_out(*_: Any) -> None:
        out[0] += 1

    def _checked_in(*_: Any) -> None:
        out[0] -= 1

    event.listen(engine.sync_engine, "checkout", _checked_out)
    event.listen(engine.sync_engine, "checkin", _checked_in)
    yield out
    event.remove(engine.sync_engine, "checkout", _checked_out)
    event.remove(engine.sync_engine, "checkin", _checked_in)


async def test_a_settle_lets_go_of_its_database_connection_while_the_classifier_thinks(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, connections_out: list[int]
) -> None:
    held_while_classifying: list[int] = []

    async def _classified(*, coverage_state: dict[str, str], **_: Any) -> dict[str, str]:
        held_while_classifying.append(connections_out[0])
        return coverage_state

    monkeypatch.setattr(background, "classify_coverage", _classified)
    session = await service.create_session(db_session, pericope=P)

    await _settle(session.id, "turn-9")

    assert held_while_classifying == [0], (
        "o settle segurava uma conexão do banco durante os ~21 s do classificador, e cada "
        "turno em reflexão tirava uma conexão do pool de todos os outros"
    )


async def test_a_bead_another_settle_lit_during_the_classifier_survives_this_one(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.database import AsyncSessionLocal

    first, second = element_keys(P)[:2]
    session = await service.create_session(db_session, pericope=P)
    engaged = CoverageStatus.ENGAGED.value

    async def _classified(*, coverage_state: dict[str, str], **_: Any) -> dict[str, str]:
        async with AsyncSessionLocal() as elsewhere:
            lit = (await service.get_session(elsewhere, session.id)).coverage_state or {}
            await service.apply_coverage(elsewhere, session.id, {**lit, first: engaged})
        return {**coverage_state, second: engaged}

    monkeypatch.setattr(background, "classify_coverage", _classified)

    await _settle(session.id, "turn-10")

    async with AsyncSessionLocal() as reading:
        stored = (await service.get_session(reading, session.id)).coverage_state or {}
    assert stored.get(second) == engaged
    assert stored.get(first) == engaged, (
        "o apply_coverage relia a sessão pelo identity map do próprio settle, com o estado "
        "de antes do classificador, e apagava a conta que outro settle acendera nesse meio"
    )
