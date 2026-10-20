from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.internalization_room import segments as segments_api
from app.services.internalization_room.llm import CACHE_BREAK
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import (
    nothing_is_read_ahead,
    played_every_part,
    press_terminei,
    room_client,
    stored_telling_back,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken
from tests.turn_harness import the_room_agent_is

PART = [(0, 1000), (1000, 2000), (2000, 3000)]
LAID_IN_PART_MS = 3400


def _nuance_on(frase: int, quote: str = "") -> dict[str, Any]:
    return {
        "kind": "nuance",
        "note": "O jeito de contar mudou.",
        "frase": frase,
        "quote": quote or f"frase {frase}",
        "story": "a história conta de outro jeito",
    }


def _names(frase: int) -> str:
    return f"Só um detalhe, na frase {frase}: vocês traduziram «frase {frase}»."


class Speaker:
    def __init__(self) -> None:
        self.line = "Vocês contaram bem."
        self.briefs: list[str] = []

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        self.briefs.append(system_prompt.replace(CACHE_BREAK, ""))
        return self.line

    def handed(self) -> list[dict[str, Any]]:
        return list(
            json.loads(self.briefs[-1].split("## The findings for the whole passage\n\n")[1])
        )


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture(autouse=True)
def quiet(monkeypatch: pytest.MonkeyPatch) -> None:
    nothing_is_read_ahead(monkeypatch)


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


async def _named_and_heard(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    session_id: str,
    part_id: str,
    nuance: dict[str, Any],
) -> None:
    analyst.readings = [{"findings": [nuance]}]
    speaker.line = _names(nuance["frase"])
    pressed = await press_terminei(
        client,
        session_id,
        report=played_every_part([part_id], duration_ms=3000),
    )
    assert pressed.status_code == 200, pressed.text
    heard = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/heard",
        json={"at": pressed.json()["check_at"]},
    )
    assert heard.status_code == 200, heard.text


async def _laid_in_and_told_again(
    client: httpx.AsyncClient, session_id: str, segment_id: str, position: int
) -> str:
    laid = (await re_record(client, session_id, segment_id, spoken(1.0))).json()["segments"]
    new = laid[position]
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{segment_id}/replace",
        data={
            "take_id": new["take_id"],
            "starts_ms": str(new["starts_ms"]),
            "ends_ms": str(new["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return str(new["take_id"])


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
    await _named_and_heard(client, analyst, speaker, session.id, part.id, _nuance_on(nuance_on))
    new_take = await _laid_in_and_told_again(client, session.id, told[laid_on - 1].id, laid_on - 1)
    analyst.readings = [{"findings": [_nuance_on(nuance_on)]}]
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
    await _named_and_heard(client, analyst, speaker, session.id, part.id, _nuance_on(3, "frase"))
    third_again = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[2].id}/replace",
        data={"take_id": part.id, "starts_ms": "2000", "ends_ms": "3000"},
        files={"file": ("trecho.m4a", b"a equipe traduziu de novo", "audio/mp4")},
    )
    assert third_again.status_code == 200, third_again.text
    new_take = await _laid_in_and_told_again(client, session.id, told[1].id, 1)
    analyst.readings = [{"findings": [_nuance_on(3, "frase")]}]
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
    await _named_and_heard(client, analyst, speaker, session.id, part.id, _nuance_on(2, "frase"))
    new_take = await _laid_in_and_told_again(client, session.id, told[1].id, 1)
    analyst.readings = [{"findings": [_nuance_on(2, "frase")]}]
    speaker.line = _names(2)

    again = await press_terminei(
        client, session.id, report=played_every_part([new_take], duration_ms=LAID_IN_PART_MS)
    )

    assert again.status_code == 200, again.text
    assert [one["frase"] for one in speaker.handed()] == [2], (
        "a frase de áudio novo herdava a nuance dita sobre a frase que a equipe regravou"
    )
