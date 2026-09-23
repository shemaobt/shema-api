"""What the bead classifier is handed each turn, and what it is allowed to move.

Her injection contract (`prompts/vendor/classifier_system_prompt.md`, runtime injection 1):
the elements go as structured entries carrying their **current status**, and only the ones
still at `not_encountered` or `surfaced`. The offer is every bead short of `engaged`, of any
scene or of none — the Scene pointer is never a scope on it — and an id that was not offered
moves nothing.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import background
from app.services.internalization_room import sessions as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.canon.elements import element_keys, elements_for
from app.services.internalization_room.classify_coverage import (
    _parse,
    _scenes_block,
    _unresolved_block,
    classify_coverage,
    classify_coverage_by_keywords,
)
from app.services.internalization_room.coverage import (
    CoverageStatus,
    initial_state,
    merge,
    remaining,
)
from app.services.internalization_room.llm import CACHE_BREAK

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


@pytest.fixture
def the_classifier_answers(monkeypatch: pytest.MonkeyPatch):
    module = sys.modules["app.services.internalization_room.classify_coverage"]

    def _install(reply: str):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            agent.system = system_prompt
            return reply

        monkeypatch.setattr(module, "call_agent", agent)
        return agent

    return _install


def _the_ids_shown(system_prompt: str) -> list[str]:
    heading = "## The coverage elements (current unresolved set)"
    block = system_prompt.split(heading, 1)[1].split("## This turn's exchange", 1)[0]
    return [entry["id"] for entry in json.loads(block.replace(CACHE_BREAK, ""))]


def test_every_element_the_classifier_is_shown_carries_its_current_status() -> None:
    keys = element_keys(P)
    state = merge(initial_state(P), pericope_num=P, engaged=[keys[4]], surfaced=[keys[5]])

    shown = json.loads(_unresolved_block(state, remaining(state, P)))

    by_id = {entry["id"]: entry for entry in shown}
    assert set(by_id[keys[5]]) == {"id", "kind", "label", "status"}, (
        "a lista chegava como `- [chave] rótulo`, sem status nenhum, e o prompt pedia "
        "'um avanço a partir do status atual' de um status que ele nunca via"
    )
    assert by_id[keys[5]]["status"] == CoverageStatus.SURFACED.value
    assert by_id[keys[5]]["kind"] == "being"
    assert by_id[keys[6]]["status"] == CoverageStatus.NOT_ENCOUNTERED.value
    assert keys[4] not in by_id, "uma conta já engajada não pode voltar e não precisa ser relida"
    assert {entry["status"] for entry in shown} == {"not_encountered", "surfaced"}


def test_a_bead_stored_under_the_retired_status_is_shown_as_surfaced_not_dropped() -> None:
    keys = element_keys(P)
    state = {**initial_state(P), keys[5]: CoverageStatus.PARTIALLY_ENGAGED.value}

    shown = {
        entry["id"]: entry["status"]
        for entry in json.loads(_unresolved_block(state, remaining(state, P)))
    }

    assert shown[keys[5]] == CoverageStatus.SURFACED.value, (
        "o prompt dela só conhece not_encountered e surfaced; mandar a palavra aposentada "
        "nomeia um status que ele não tem, e não mandar a conta congela a conta para sempre"
    )


def test_the_scenes_are_named_by_the_bare_id_the_prompt_asks_for_and_their_title() -> None:
    block = _scenes_block(P)

    assert json.loads(block) == [
        {"id": "S1", "title": "Famine and exile to Moab"},
        {"id": "S2", "title": "Death of Elimelech"},
        {"id": "S3", "title": "Marriages and time passing"},
        {"id": "S4", "title": "Deaths of the sons"},
    ], (
        "a lista de cenas chegava como `- [scene:1] …`, a forma prefixada que o mesmo "
        "prompt manda nunca usar no escopo do reconto"
    )
    assert "scene:" not in block


def test_a_decision_buried_in_a_sentence_of_prose_still_moves_the_beads() -> None:
    wrapped = (
        "Sure — here is the classification for this exchange: "
        '{"decisions": [{"element_id": "scene:1", "new_status": "engaged", "evidence": "told it"}]}'
        " Let me know if you need anything else."
    )

    assert _parse(wrapped)["engaged"] == ["scene:1"], (
        "o leitor aceitava JSON nu ou cercado e mais nada; um objeto embrulhado numa frase "
        "era 'JSON ilegível' e a classificação do turno sumia em silêncio"
    )


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


async def test_a_settle_offers_every_bead_short_of_engaged_whatever_scene_holds_the_pointer(
    db_session: AsyncSession, the_classifier_answers, monkeypatch: pytest.MonkeyPatch
) -> None:
    ruth_in_scene_three = "being:S3:B9"
    agent = the_classifier_answers(
        json.dumps({"decisions": [{"element_id": ruth_in_scene_three, "new_status": "engaged"}]})
    )
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)
    worked = [element.key for element in elements_for(P) if element.scene == 1]
    worked.remove("absence:1")
    await service.apply_coverage(
        db_session,
        session.id,
        merge(initial_state(P), pericope_num=P, surfaced=["absence:1"], engaged=worked),
    )
    for team_utterance, guide_response in [
        ("a famine came and the family left Bethlehem", "and then Elimelech died there"),
        ("Elimelech died and Naomi was left with her sons", "and what did the sons do"),
        ("the sons married Orpah and Ruth and ten years passed", "and after those years"),
        ("then Mahlon and Chilion died and the woman was alone", "tell me about her"),
    ]:
        await service.append_exchange(
            db_session, session, team_utterance=team_utterance, guide_response=guide_response
        )

    await background.settle_coverage(
        session_id=session.id,
        turn_id="turn-5",
        team_utterance="Ruth stayed with Naomi in Moab",
        guide_response="what happened to the two women",
        pericope_num=P,
    )

    assert set(_the_ids_shown(agent.system)) == set(element_keys(P)) - set(worked), (
        "com o silêncio da cena 1 só levantado, o ponteiro ficava na cena 1 e o classificador "
        "nunca via uma conta das cenas 2, 3 e 4, por mais que a equipe as contasse"
    )
    await db_session.refresh(session)
    assert session.coverage_state[ruth_in_scene_three] == CoverageStatus.ENGAGED.value, (
        "a resposta do classificador sobre uma conta da cena 3 tem de chegar ao registro"
    )
    assert session.coverage_state["absence:1"] == CoverageStatus.SURFACED.value, (
        "o classificador não nomeou o silêncio: ele fica onde estava"
    )


async def test_an_id_the_classifier_was_not_offered_this_turn_moves_nothing(
    the_classifier_answers, caplog
) -> None:
    naomi_before_the_scenes = "being:B3"
    stored = {**initial_state(P), naomi_before_the_scenes: CoverageStatus.NOT_ENCOUNTERED.value}
    the_classifier_answers(
        json.dumps(
            {
                "decisions": [
                    {"element_id": naomi_before_the_scenes, "new_status": "engaged"},
                    {"element_id": "scene:1", "new_status": "engaged"},
                ]
            }
        )
    )

    with caplog.at_level(logging.WARNING):
        settled = await classify_coverage(
            coverage_state=stored,
            team_utterance="a famine came and Naomi left for Moab",
            guide_response="tell me what happened next",
            classifier_prompt=CLASSIFIER,
            pericope_num=P,
            settings=_settings(),
        )

    assert settled["scene:1"] == CoverageStatus.ENGAGED.value
    assert settled[naomi_before_the_scenes] == CoverageStatus.NOT_ENCOUNTERED.value, (
        "uma chave que o registro guardado ainda tem mas o mapa não tem mais passava pelo "
        "merge como qualquer outra: o modelo movia uma conta que o turno nunca ofereceu"
    )
    assert "not offered" in caplog.text


async def test_the_keyword_classifier_moves_beads_from_the_words_alone_with_no_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = sys.modules["app.services.internalization_room.classify_coverage"]

    async def never(**_: Any) -> str:
        raise AssertionError("o classificador determinístico chamou o provedor")

    monkeypatch.setattr(module, "call_agent", never)

    settled = await classify_coverage_by_keywords(
        coverage_state=initial_state(P),
        team_utterance="Naomi and her husband went away because of the famine, Ruth too",
        guide_response="They left Bethlehem of Judah for the fields of Moab.",
        pericope_num=P,
    )

    assert settled["being:S1:B3"] == CoverageStatus.ENGAGED.value, (
        "as palavras da equipe tocam o rótulo de Noemi e a conta tem de subir a engaged"
    )
    assert settled["object:S1:O1"] == CoverageStatus.ENGAGED.value
    assert settled["place:S1:PL1"] == CoverageStatus.SURFACED.value, (
        "Belém só saiu da boca do Guia: levantada, não engajada"
    )
    assert settled["place:S1:PL2"] == CoverageStatus.SURFACED.value
    assert settled["being:S1:B2"] == CoverageStatus.NOT_ENCOUNTERED.value, (
        "'her husband' não toca o rótulo de Elimeleque; nada de engajamento inventado"
    )
    assert settled["being:S3:B9"] == CoverageStatus.ENGAGED.value, (
        "Rute é da cena 3 e nenhuma conta aquém de engaged fica fora da lista, em cena nenhuma"
    )
