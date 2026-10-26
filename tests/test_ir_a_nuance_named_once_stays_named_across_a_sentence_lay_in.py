from __future__ import annotations

from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import (
    played_every_part,
    press_terminei,
    room_client,
    stored_telling_back,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import (
    PART,
    Speaker,
    laid_in_and_told_again,
    named_and_heard,
    names_the_nuance_on,
    nuance_of_frase,
    rehearsed_in_wav,
)
from tests.turn_harness import the_room_agent_is

LAID_IN_PART_MS = 3400


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture(autouse=True)
def transcriber(monkeypatch: pytest.MonkeyPatch) -> None:
    async def said(*_: Any, **__: Any) -> str:
        return "a frase nova traduzida"

    monkeypatch.setattr(segments_api, "heard", said)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch):
    return the_analyst_is_scripted(monkeypatch)


@pytest.fixture()
def speaker(monkeypatch: pytest.MonkeyPatch) -> Speaker:
    the_room_speaks(monkeypatch)
    voice = Speaker()
    the_room_agent_is(monkeypatch, turn=voice)
    return voice


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


@pytest.mark.parametrize(
    ("nuance_on", "laid_on"),
    [(3, 2), (1, 2)],
    ids=["a frase after the laid-in one", "a frase before the laid-in one"],
)
async def test_a_nuance_heard_named_is_not_named_again_after_another_frase_is_laid_in(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    db_session: AsyncSession,
    store: MemoryStore,
    nuance_on: int,
    laid_on: int,
) -> None:
    session, (part,), (told,) = await rehearsed_in_wav(db_session, store, [PART])
    await named_and_heard(client, analyst, speaker, session.id, part.id, nuance_of_frase(nuance_on))
    new_take = await laid_in_and_told_again(client, session.id, told[laid_on - 1].id, laid_on - 1)
    analyst.readings = [{"findings": [nuance_of_frase(nuance_on)]}]
    speaker.line = "Vocês contaram bem."

    again = await press_terminei(
        client,
        session.id,
        report=played_every_part([new_take], duration_ms=LAID_IN_PART_MS),
    )

    assert again.status_code == 200, again.text
    assert speaker.handed() == [], (
        "a regravação de uma frase fazia a voz nomear de novo a nuance de outra frase"
    )
    kept = (await stored_telling_back(db_session, session)).checks
    assert [one.voiced for one in kept[-1].nuances] == ["before"], (
        "a nuance já dita perdia o áudio em que foi dita e a rodada não a reconhecia"
    )


async def test_a_frase_told_again_on_the_same_audio_keeps_its_nuance_named_through_a_lay_in(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    db_session: AsyncSession,
    store: MemoryStore,
) -> None:
    session, (part,), (told,) = await rehearsed_in_wav(db_session, store, [PART])
    await named_and_heard(
        client, analyst, speaker, session.id, part.id, nuance_of_frase(3, "frase")
    )
    third_again = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[2].id}/replace",
        data={"take_id": part.id, "starts_ms": "2000", "ends_ms": "3000"},
        files={"file": ("trecho.m4a", b"a equipe traduziu de novo", "audio/mp4")},
    )
    assert third_again.status_code == 200, third_again.text
    new_take = await laid_in_and_told_again(client, session.id, told[1].id, 1)
    analyst.readings = [{"findings": [nuance_of_frase(3, "frase")]}]
    speaker.line = "Vocês contaram bem."

    again = await press_terminei(
        client, session.id, report=played_every_part([new_take], duration_ms=LAID_IN_PART_MS)
    )

    assert again.status_code == 200, again.text
    assert speaker.handed() == [], (
        "a frase traduzida de novo sobre o mesmo áudio perdia a nuance dita ao mover o áudio"
    )


async def test_the_frase_whose_sentence_was_recorded_again_may_have_its_nuance_named_again(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    db_session: AsyncSession,
    store: MemoryStore,
) -> None:
    session, (part,), (told,) = await rehearsed_in_wav(db_session, store, [PART])
    await named_and_heard(
        client, analyst, speaker, session.id, part.id, nuance_of_frase(2, "frase")
    )
    new_take = await laid_in_and_told_again(client, session.id, told[1].id, 1)
    analyst.readings = [{"findings": [nuance_of_frase(2, "frase")]}]
    speaker.line = names_the_nuance_on(2)

    again = await press_terminei(
        client, session.id, report=played_every_part([new_take], duration_ms=LAID_IN_PART_MS)
    )

    assert again.status_code == 200, again.text
    assert [one["frase"] for one in speaker.handed()] == [2], (
        "a frase de áudio novo herdava a nuance dita sobre a frase que a equipe regravou"
    )
