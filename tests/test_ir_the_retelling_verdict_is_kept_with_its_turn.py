"""ENG-1378 (b) — the retelling verdict the coverage reader returns is kept with its turn.

Her classifier answers a retelling verdict beside its decisions (her classifier.ts:16-20,
46-52); ours asked for it in her prompt and then forbade it in the answer's schema, so
the verdict never came back and no take could ever be kept.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import background
from app.services.internalization_room import sessions as service
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.classify_coverage import classify_coverage
from app.services.internalization_room.coverage import initial_state
from tests.turn_harness import the_room_agent_is

P = "P01"
CLASSIFIER = default_prompt(IRPromptKey.COVERAGE_CLASSIFIER)["prompt"]
TOLD = "Elimelech foi com Noemi e os dois filhos para Moabe por causa da fome."
AFFIRMED = "Isso. Vocês contaram a cena inteira."


@asynccontextmanager
async def _handed(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield db_session


def the_reader_says(monkeypatch: pytest.MonkeyPatch, *answers: dict[str, Any]) -> None:
    replies = [json.dumps({"decisions": [], **answer}) for answer in answers]

    async def reader(**_: Any) -> str:
        return replies.pop(0) if len(replies) > 1 else replies[0]

    the_room_agent_is(monkeypatch, classifier=reader)


async def _settled(session_id: str, turn_number: int) -> None:
    await background.settle_coverage(
        session_id=session_id,
        turn_id=f"turno-{turn_number}",
        turn_number=turn_number,
        team_utterance=TOLD,
        guide_response=AFFIRMED,
        pericope_num=P,
    )


async def test_the_answer_the_classifier_is_bound_to_admits_her_retelling_verdict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    schemas: list[dict[str, Any]] = []

    async def reader(*, schema: dict[str, Any], **_: Any) -> str:
        schemas.append(schema)
        return '{"decisions": []}'

    the_room_agent_is(monkeypatch, classifier=reader)

    await classify_coverage(
        coverage_state=initial_state(P),
        team_utterance=TOLD,
        guide_response=AFFIRMED,
        classifier_prompt=CLASSIFIER,
        pericope_num=P,
    )

    assert schemas[0]["required"] == ["decisions"]
    assert schemas[0]["properties"]["retelling"] == {
        "type": "object",
        "properties": {"scope": {"type": "string"}, "approved": {"type": "boolean"}},
        "required": ["scope", "approved"],
        "additionalProperties": False,
    }, (
        "o prompt dela pedia o veredito da recontagem e o esquema da resposta o proibia, "
        "então o veredito nunca voltava"
    )


async def test_each_settled_turn_keeps_the_retelling_verdict_its_reading_returned(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    the_reader_says(monkeypatch, {"retelling": {"scope": "S1", "approved": False}})
    await _settled(session.id, 1)
    the_reader_says(monkeypatch, {"retelling": {"scope": "S1", "approved": True}})
    await _settled(session.id, 2)

    await db_session.refresh(session)
    assert session.retellings == {
        "1": {"scope": "S1", "approved": False},
        "2": {"scope": "S1", "approved": True},
    }, "o veredito da recontagem voltava do leitor e era jogado fora, recusado ou aprovado"


async def test_a_verdict_read_after_a_newer_turn_landed_stays_on_the_turn_it_judged(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)
    await service.append_opening(db_session, session, guide_response="Vamos começar.")
    await service.append_exchange(db_session, session, team_utterance=TOLD, guide_response=AFFIRMED)
    await service.append_exchange(
        db_session, session, team_utterance="E depois?", guide_response="Contem o resto."
    )

    the_reader_says(monkeypatch, {"retelling": {"scope": "S1", "approved": True}})
    await _settled(session.id, 1)

    await db_session.refresh(session)
    assert session.retellings == {"1": {"scope": "S1", "approved": True}}, (
        "a leitura voltava depois do turno seguinte e o veredito caía no turno errado"
    )


async def test_a_verdict_names_a_scene_of_the_passage_or_the_whole_and_nothing_else(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    for number, scope in enumerate(["scene:S2", "S9", "whole"], start=1):
        the_reader_says(monkeypatch, {"retelling": {"scope": scope, "approved": True}})
        await _settled(session.id, number)

    await db_session.refresh(session)
    assert session.retellings == {
        "1": {"scope": "S2", "approved": True},
        "3": {"scope": "whole", "approved": True},
    }, "uma cena que a passagem não tem virava veredito, e o id com 'scene:' não era a cena"


async def test_readings_of_one_turn_that_do_not_agree_on_the_verdict_keep_none(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(background, "AsyncSessionLocal", lambda: _handed(db_session))
    session = await service.create_session(db_session, pericope=P)

    approved = {"retelling": {"scope": "S1", "approved": True}}
    the_reader_says(monkeypatch, approved, {"retelling": {"scope": "S1", "approved": False}})
    await _settled(session.id, 1)
    the_reader_says(monkeypatch, approved, {})
    await _settled(session.id, 2)

    await db_session.refresh(session)
    assert session.retellings is None, (
        "uma leitura aprovava e outra recusava ou calava, e a primeira a chegar decidia"
    )
