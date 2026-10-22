"""ENG-1685 — a verdict that was being written when a sentence was laid in does not confer.

A sentence lay-in keeps the ids of the frases it re-points, so the check's own comparison, whether
the stretches it read are the stretches that stand, cannot tell that one of them was laid in
since. A verdict that read before the lay-in and wrote after it was merged over the lay-in's
uncheck with the `checked` it carried, and the passage stood checked with a sentence nobody had
translated.

The sentence is laid in from a session of its own, right before the verdict's exchange is
written, the way a re-record from the other tablet would be.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room import verdict_round
from app.services.internalization_room.sentences import lay_in_a_sentence
from app.services.internalization_room.sessions import back_translation_of, get_session
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import PREFIX
from tests.room_harness import (
    heard_every_part,
    press_terminei,
    room_client,
    the_analyst_is_scripted,
    the_bucket_is_in_memory,
    the_room_speaks,
)
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken
from tests.turn_harness import the_room_agent_is

SAID = "Vocês contaram bem."


class Speaker:
    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        return SAID


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as room:
        yield room


async def test_a_verdict_written_after_a_sentence_was_laid_in_leaves_the_passage_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())
    session, _, ((frase, _other),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    report = await heard_every_part(db_session, session.id, duration_ms=2000)
    written = verdict_round.append_exchange

    async def written_after_a_sentence_was_laid_in(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as laying_db:
            await lay_in_a_sentence(
                laying_db,
                await get_session(laying_db, session.id),
                await laying_db.get(IRSegment, frase.id),
                sentence_id="sentence-0001",
                audio=spoken(1.0),
                device_id="tablet-da-equipe",
                store=store,
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_a_sentence_was_laid_in)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert [one.sentence_id for one in stored.sentences] == ["sentence-0001"]
    assert (stored.checked, stored.verdict) == (False, None), (
        "o veredito que leu antes da frase regravada e gravou depois dela devolvia o checked, "
        "e a passagem ficava conferida com uma frase que ninguém traduziu"
    )
    assert [one.spoken for one in stored.checks] == [SAID], (
        "a rodada do veredito que chegou depois da frase regravada não ficava guardada"
    )


async def test_a_verdict_on_a_frase_told_again_after_its_sentence_was_laid_in_still_confers(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())

    async def said(*_: Any, **__: Any) -> str:
        return "a frase nova traduzida"

    monkeypatch.setattr(segments_api, "heard", said)
    session, _, ((frase, _other),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    laid = (await re_record(client, session.id, frase.id, spoken(1.0))).json()["segments"][0]
    told = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{frase.id}/replace",
        data={
            "take_id": laid["take_id"],
            "starts_ms": str(laid["starts_ms"]),
            "ends_ms": str(laid["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    report = await heard_every_part(db_session, session.id, duration_ms=3000)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert [one.sentence_id for one in stored.sentences] == ["sentence-0001"]
    assert (stored.checked, stored.verdict is not None) == (True, True), (
        "uma frase regravada que já tinha sido traduzida de novo antes da conferência "
        "deixava a passagem sem conferir"
    )
