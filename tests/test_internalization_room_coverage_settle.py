import json
import logging
import sys
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey, IRSessionStatus
from app.services.internalization_room import sessions as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.classify_coverage import (
    _parse,
    _unresolved_block,
    classify_coverage,
)
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
        recording_consent_given=True,
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


def test_a_decision_lands_in_the_bucket_its_new_status_names() -> None:
    reply = json.dumps(
        {
            "decisions": [
                {"element_id": "scene:1", "new_status": "engaged", "evidence": "contaram a cena"},
                {"element_id": "scene:2", "new_status": "surfaced", "evidence": "o Guia citou"},
                {"element_id": "scene:3", "new_status": "partially_engaged", "evidence": "ecoaram"},
            ]
        }
    )

    verdict = _parse(reply)

    assert verdict == {
        "surfaced": ["scene:2"],
        "partially_engaged": ["scene:3"],
        "engaged": ["scene:1"],
    }, (
        "a mesa de roteamento tinha duas casas e o prompt manda três, então toda decisão "
        "partially_engaged virava aviso no log em vez de conta movida"
    )


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
    session = await service.create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
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


async def test_a_passage_the_team_only_echoed_closes_like_one_it_worked_on_its_own(
    db_session: AsyncSession, patch_classifier
) -> None:
    patch_classifier(_whole_passage_partially_engaged(P))
    session = await service.create_session(db_session, pericope=P, bridge_mode="guided_microchecks")
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

    assert session.status is IRSessionStatus.DONE, (
        "o piso foi rebaixado justamente para aceitar partially_engaged, e o parser "
        "descartava o único status que o alcançava — a passagem trabalhada na deixa "
        "do Guia ficava aberta para sempre"
    )


async def test_a_passage_the_team_only_echoed_drops_the_coverage_blocker_from_the_release(
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

    assert "coverage_floor_not_met" not in blockers, (
        "as regras de preservação chegam à sala como a equipe assumindo o que o Guia "
        "notou, e nenhuma delas era escrita — a soltura respondia piso não atingido "
        "por trabalho que existiu"
    )


def test_a_reply_with_no_decisions_says_so_instead_of_reading_as_no_change(caplog) -> None:
    with caplog.at_level(logging.WARNING):
        verdict = _parse(json.dumps({"retelling": {"scope": "S1", "approved": True}}))

    assert verdict == {"surfaced": [], "partially_engaged": [], "engaged": []}
    assert "no decisions list" in caplog.text, (
        "uma resposta sem o array voltava vazia calada, igualzinho a um turno "
        "em que nada mudou — foi esse silêncio que escondeu o bug por dois releases"
    )


def test_a_decision_carrying_an_unknown_status_is_named_in_the_log(caplog) -> None:
    reply = json.dumps({"decisions": [{"element_id": "scene:1", "new_status": "not_encountered"}]})

    with caplog.at_level(logging.WARNING):
        verdict = _parse(reply)

    assert verdict == {"surfaced": [], "partially_engaged": [], "engaged": []}
    assert "unusable decision" in caplog.text, (
        "um status que o parser não roteia sumia sem deixar rastro, "
        "e a conta parada parecia decisão do classificador"
    )


def test_a_reply_the_parser_cannot_read_buckets_nothing_instead_of_failing() -> None:
    unreadable = _parse("desculpa, não consegui classificar")
    not_an_object = _parse(json.dumps(["surfaced", "engaged"]))

    assert unreadable == not_an_object == {"surfaced": [], "partially_engaged": [], "engaged": []}


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
            "partially_engaged",
            "engaged",
        )
        if name not in agent.system
    ]

    assert missing == [], (
        "o parser lia chaves que o prompt nunca pediu, e nenhum teste olhava as duas "
        "pontas ao mesmo tempo, que é como a deriva atravessou dois releases"
    )


def _as_the_list_prints_it(pericope: str, key: str) -> str:
    """The element exactly as the classifier is shown it, read off the real renderer."""
    for line in _unresolved_block(initial_state(pericope), pericope).splitlines():
        if line.startswith(f"- [{key}]"):
            return line.removeprefix("- ")
    raise AssertionError(f"{key} is not in the unresolved block for {pericope}")


@pytest.mark.parametrize(
    "named",
    [
        "object:O1",
        "[object:O1] רָעָב / famine",
        "- [object:O1] רָעָב / famine",
    ],
)
def test_the_key_is_read_out_of_the_line_the_model_echoes_back(named: str) -> None:
    reply = json.dumps(
        {
            "decisions": [
                {
                    "element_id": named,
                    "new_status": "engaged",
                    "evidence": "nomearam a fome com as próprias palavras",
                }
            ]
        }
    )

    assert _parse(reply)["engaged"] == ["object:O1"], (
        "o prompt pede o id da lista fornecida e a lista imprime `- [chave] rótulo`, "
        "então era a linha inteira que voltava"
    )


async def test_an_element_named_the_way_the_list_prints_it_still_moves_the_bead(
    patch_classifier,
) -> None:
    keys = element_keys(P)
    patch_classifier(
        json.dumps(
            {
                "decisions": [
                    {
                        "element_id": _as_the_list_prints_it(P, keys[0]),
                        "new_status": "engaged",
                        "evidence": "contaram a cena",
                    }
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
        "toda decisão caía como elemento desconhecido no merge, então o classificador "
        "acertava a troca e o colar não movia uma conta em sessão nenhuma"
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
