"""The coverage classification reaches the necklace whole, or not at all.

A telling that walks the whole passage in one turn used to be offered to the model as one
reading of every bead; the reply ran out of room mid-list, the JSON came back cut, and not
one bead lit. The beads are now read in readings that fit, a reading cut short is read
again in halves, and no reading's decisions reach the necklace unless every reading landed.
"""

from __future__ import annotations

import json
import logging
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
from app.services.internalization_room.canon.elements import element_keys
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import CoverageStatus, initial_state
from app.services.internalization_room.llm import CACHE_BREAK
from tests.turn_harness import the_room_agent_is

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
WHOLE_TELLING = (
    "In the days of the judges a famine came, and Elimelech of Bethlehem went with Naomi and "
    "their sons Mahlon and Chilion to the fields of Moab. Elimelech died there. The sons "
    "married Orpah and Ruth, and after ten years Mahlon and Chilion died too, and Naomi was "
    "left without her husband and her boys."
)
GUIDE_RESPONSE = "And what did Naomi do then?"


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


def _the_ids_shown(system_prompt: str) -> list[str]:
    heading = "## The coverage elements (current unresolved set)"
    block = system_prompt.split(heading, 1)[1].split("## This turn's exchange", 1)[0]
    return [entry["id"] for entry in json.loads(block.replace(CACHE_BREAK, ""))]


def _all_engaged(ids: list[str]) -> str:
    return json.dumps({"decisions": [{"element_id": key, "new_status": "engaged"} for key in ids]})


@pytest.fixture
def the_classifier_reads(monkeypatch: pytest.MonkeyPatch):
    def _install(cuts_short):
        async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            ids = _the_ids_shown(system_prompt)
            agent.readings.append((system_prompt, ids))
            whole = _all_engaged(ids)
            return whole[: len(whole) // 2] if cuts_short(ids, len(agent.readings)) else whole

        agent.readings = []
        the_room_agent_is(monkeypatch, classifier=agent)
        return agent

    return _install


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


async def test_a_telling_of_the_whole_passage_lights_every_bead_it_touched(
    db_session: AsyncSession, the_classifier_reads, monkeypatch: pytest.MonkeyPatch
) -> None:
    the_classifier_reads(lambda ids, _: len(ids) > 20)
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    await background.settle_coverage(
        session_id=session.id,
        turn_id="turn-1",
        team_utterance=WHOLE_TELLING,
        guide_response=GUIDE_RESPONSE,
        pericope_num=P,
    )

    await db_session.refresh(session)
    lit = [
        key
        for key in element_keys(P)
        if session.coverage_state[key] == CoverageStatus.ENGAGED.value
    ]
    assert lit == element_keys(P), (
        "a passagem inteira contada num turno deixava o colar em 0 de 44: a resposta do "
        "modelo sobre as 44 contas vinha cortada e nenhuma decisão chegava ao colar"
    )


async def test_a_reading_cut_short_once_is_read_again_and_every_bead_still_lands(
    the_classifier_reads, caplog
) -> None:
    the_classifier_reads(lambda _, call: call == 1)

    with caplog.at_level(logging.WARNING):
        settled = await classify_coverage(
            coverage_state=initial_state(P),
            team_utterance=WHOLE_TELLING,
            guide_response=GUIDE_RESPONSE,
            classifier_prompt=CLASSIFIER,
            pericope_num=P,
            settings=_settings(),
        )

    assert {settled[key] for key in element_keys(P)} == {CoverageStatus.ENGAGED.value}, (
        "uma leitura cortada uma vez perdia as contas dela de vez"
    )
    assert "read again" in caplog.text, "a releitura tem de aparecer no log"


async def test_a_bead_whose_reading_never_lands_holds_back_every_other_readings_decisions(
    the_classifier_reads,
) -> None:
    stubborn = element_keys(P)[30]
    the_classifier_reads(lambda ids, _: stubborn in ids)
    before = initial_state(P)

    settled = await classify_coverage(
        coverage_state=before,
        team_utterance=WHOLE_TELLING,
        guide_response=GUIDE_RESPONSE,
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    assert settled == before, (
        "a classificação nunca se aplica em parte: se uma leitura não chega, "
        "as decisões das outras não chegam ao colar"
    )


async def test_every_reading_is_shown_the_same_exchange_and_each_bead_exactly_once(
    the_classifier_reads,
) -> None:
    agent = the_classifier_reads(lambda _ids, _call: False)

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance=WHOLE_TELLING,
        guide_response=GUIDE_RESPONSE,
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    shown = [key for _, ids in agent.readings for key in ids]
    assert sorted(shown) == sorted(element_keys(P)), (
        "cada conta oferecida é mostrada a exatamente uma leitura"
    )
    for system_prompt, _ in agent.readings:
        assert WHOLE_TELLING in system_prompt
        assert GUIDE_RESPONSE in system_prompt


async def test_a_reading_that_names_a_bead_it_was_not_shown_moves_nothing_for_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = element_keys(P)[0]
    named_elsewhere: list[str] = []

    async def agent(*, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        ids = _the_ids_shown(system_prompt)
        if first not in ids:
            return _all_engaged([])
        stray = next(key for key in element_keys(P) if key not in ids)
        named_elsewhere.append(stray)
        return _all_engaged([first, stray])

    the_room_agent_is(monkeypatch, classifier=agent)

    settled = await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance=WHOLE_TELLING,
        guide_response=GUIDE_RESPONSE,
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
        settings=_settings(),
    )

    assert settled[first] == CoverageStatus.ENGAGED.value
    assert settled[named_elsewhere[0]] == CoverageStatus.NOT_ENCOUNTERED.value, (
        "uma leitura movia uma conta que só outra leitura foi mostrada, "
        "e que essa outra leitura não nomeou"
    )
