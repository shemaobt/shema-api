from __future__ import annotations

import json
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSegment
from app.services.internalization_room import verdict_round
from app.services.internalization_room.hard_stretches import capture_and_note_a_hard_stretch
from app.services.internalization_room.sessions import (
    back_translation_of,
    get_session,
    save_back_translation,
)
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
from tests.sentence_harness import rehearsed_in_wav
from tests.turn_harness import the_room_agent_is

SAID = "Vocês contaram bem."
RETOLD = "a frase contada de novo, até a pausa nova"


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


def the_pause_moves_just_before_the_exchange_is_written(
    monkeypatch: pytest.MonkeyPatch,
    rival_factory: async_sessionmaker[AsyncSession],
    session_id: str,
    last: IRSegment,
) -> None:
    written = verdict_round.append_exchange

    async def written_after_the_pause_moved(*args: Any, **kwargs: Any) -> Any:
        async with rival_factory() as moving_db:
            await capture_and_note_a_hard_stretch(
                moving_db,
                await get_session(moving_db, session_id),
                take_id=last.take_id,
                starts_ms=last.starts_ms,
                ends_ms=1800,
                bridge_take_id="retro-movida",
                transcript=RETOLD,
                replaces=await moving_db.get(IRSegment, last.id),
            )
        return await written(*args, **kwargs)

    monkeypatch.setattr(verdict_round, "append_exchange", written_after_the_pause_moved)


async def test_a_verdict_written_after_the_last_pause_moved_leaves_the_passage_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())
    session, _, ((_first, last),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    report = await heard_every_part(db_session, session.id, duration_ms=2000)
    the_pause_moves_just_before_the_exchange_is_written(
        monkeypatch, rival_factory, session.id, last
    )

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert (stored.checked, stored.verdict) == (False, None), (
        "o veredito que leu antes da pausa movida e gravou depois dela devolvia o checked, "
        "e a passagem ficava conferida com uma frase que mudou de fim"
    )
    assert [one.spoken for one in stored.checks] == [SAID], (
        "a rodada do veredito que chegou depois da pausa movida não ficava guardada"
    )


async def test_a_second_round_written_after_the_last_pause_moved_leaves_the_passage_unchecked(
    client,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    the_analyst_is_scripted(monkeypatch)
    the_room_speaks(monkeypatch)
    the_room_agent_is(monkeypatch, turn=Speaker())
    session, _, ((first, last),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    already_read = back_translation_of(session)
    already_read.scope = session.pericope
    already_read.analysed_segment_ids = [first.id, last.id]
    await save_back_translation(db_session, session, already_read)
    report = await heard_every_part(db_session, session.id, duration_ms=2000)
    the_pause_moves_just_before_the_exchange_is_written(
        monkeypatch, rival_factory, session.id, last
    )

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert (stored.checked, stored.verdict) == (False, None), (
        "a segunda rodada, com a passagem já sem conferir, gravava o checked de uma frase "
        "que a pausa movida durante a rodada já tinha trocado"
    )


async def test_a_verdict_that_starts_after_the_last_pause_moved_still_confers(
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
        return RETOLD

    monkeypatch.setattr(segments_api, "heard", said)
    session, _, ((_first, last),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    moved = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{last.id}/replace",
        data={
            "take_id": last.take_id,
            "starts_ms": str(last.starts_ms),
            "ends_ms": "1800",
        },
        files={"file": ("frase.wav", b"a frase dita de novo", "audio/wav")},
    )
    assert moved.status_code == 200, moved.text
    report = await heard_every_part(db_session, session.id, duration_ms=2000)

    pressed = await press_terminei(client, session.id, report=report)
    assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert (stored.checked, stored.verdict is not None) == (True, True), (
        "uma pausa movida antes de a rodada começar deixava a passagem sem conferir"
    )


async def test_a_move_that_read_before_another_move_does_not_take_the_count_back_under_a_verdict(
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
        return RETOLD

    monkeypatch.setattr(segments_api, "heard", said)
    session, _, ((_a, last_of_one), (_b, last_of_two)) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)], [(0, 1000), (1000, 2000)]]
    )
    async with rival_factory() as moving_db:
        read_before_any_move = await get_session(moving_db, session.id)
        first = await client.post(
            f"{PREFIX}/sessions/{session.id}/segments/{last_of_one.id}/replace",
            data={
                "take_id": last_of_one.take_id,
                "starts_ms": str(last_of_one.starts_ms),
                "ends_ms": "1800",
            },
            files={"file": ("frase.wav", b"a frase dita de novo", "audio/wav")},
        )
        assert first.status_code == 200, first.text
        report = await heard_every_part(db_session, session.id, duration_ms=2000)
        written = verdict_round.append_exchange

        async def written_after_a_move_that_read_before_the_first(*args: Any, **kwargs: Any) -> Any:
            await capture_and_note_a_hard_stretch(
                moving_db,
                read_before_any_move,
                take_id=last_of_two.take_id,
                starts_ms=last_of_two.starts_ms,
                ends_ms=1800,
                bridge_take_id="retro-movida",
                transcript=RETOLD,
                replaces=await moving_db.get(IRSegment, last_of_two.id),
                state=back_translation_of(read_before_any_move),
            )
            return await written(*args, **kwargs)

        monkeypatch.setattr(
            verdict_round, "append_exchange", written_after_a_move_that_read_before_the_first
        )

        pressed = await press_terminei(client, session.id, report=report)
        assert pressed.status_code == 200, pressed.text

    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
    assert stored.pauses_moved == 2, (
        "a segunda pausa movida, que leu o estado antes da primeira, gravava 1 por cima de 1"
    )
    assert (stored.checked, stored.verdict) == (False, None), (
        "o veredito que leu a primeira pausa movida conferia a passagem quando a segunda, "
        "que tinha lido antes dela, devolvia a contagem ao que ele já tinha lido"
    )
