"""The telling-back is read as soon as nothing is left to tell or hear, not at `terminei`.

Every case drives the room over HTTP, with each request on a session of its own the way the
deployed app gives one, and counts what the analyst was asked: a reading served from the one
already made and a reading made again agree on every field of the answer but that count.
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import back_translation as bt_api
from app.api.internalization_room import segments as segments_api
from app.core.config import get_settings
from app.db.models.internalization_room import IRSegment, IRTake
from app.services.internalization_room import back_translation as bt_service
from app.services.internalization_room import llm, usage
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.takes import take_by_id
from tests.hard_stretch_harness import MemoryStore
from tests.release_harness import KEY, PREFIX, TABLET
from tests.room_harness import (
    CORRECTION_MARK,
    Room,
    ScriptedAnalyst,
    a_piece_still_to_be_told,
    after,
    another_rehearsal_take,
    played_every_part,
    press_terminei,
    rehearsed_in_parts_of,
    room_client,
    the_bucket_is_in_memory,
    the_room_speaks,
    the_transcriber_says,
)

AN_ADDITION = {"findings": [{"kind": "addition", "note": "Boaz não está nesta cena.", "chunk": 2}]}


class Analyst(ScriptedAnalyst):
    def __init__(self) -> None:
        super().__init__()
        self.whole_readings = 0

    async def __call__(self, *, system_prompt: str, user_content: str, **_: Any) -> str:
        if CORRECTION_MARK not in system_prompt:
            self.whole_readings += 1
        return await super().__call__(system_prompt=system_prompt, user_content=user_content)


@pytest.fixture()
def analyst(monkeypatch: pytest.MonkeyPatch) -> Analyst:
    reader = Analyst()
    monkeypatch.setattr(bt_service, "call_agent", reader)
    return reader


@pytest.fixture()
def room(monkeypatch: pytest.MonkeyPatch) -> Room:
    return the_room_speaks(monkeypatch)


@pytest.fixture(autouse=True)
def bucket(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    the_transcriber_says(monkeypatch, [])
    monkeypatch.setattr(segments_api, "heard", bt_api.heard)
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
def per_request(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


async def _nothing_read_ahead(**_: Any) -> None:
    return None


async def _tell(
    client: httpx.AsyncClient,
    session_id: str,
    part: IRTake,
    *,
    starts_ms: int,
    ends_ms: int,
    again: bool = False,
) -> httpx.Response:
    data = {"take_id": part.id, "starts_ms": str(starts_ms), "ends_ms": str(ends_ms)}
    if again:
        data["retelling"] = "true"
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/back-translation/chunks",
        headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
        data=data,
        files={"file": ("trecho.m4a", b"um trecho contado", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return told


async def _tell_again(
    client: httpx.AsyncClient, session_id: str, stretch: IRSegment
) -> httpx.Response:
    told = await client.post(
        f"{PREFIX}/sessions/{session_id}/segments/{stretch.id}/replace",
        headers={"X-Room-Key": KEY, "X-Room-Device": TABLET},
        data={
            "take_id": stretch.take_id,
            "starts_ms": str(stretch.starts_ms),
            "ends_ms": str(stretch.ends_ms),
        },
        files={"file": ("de-novo.m4a", b"contado de novo", "audio/mp4")},
    )
    assert told.status_code == 200, told.text
    return told


async def _a_second_stretch_after_the_first_terminei(
    client: httpx.AsyncClient, db: AsyncSession, analyst: Analyst
) -> tuple[str, str]:
    session, (part,) = await rehearsed_in_parts_of(db, [1])
    first = await press_terminei(client, session.id, report=played_every_part([part.id]))
    assert first.status_code == 200, first.text
    analyst.readings = [AN_ADDITION]
    await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)
    second = (await final_segments(db, session.id))[-1]
    return session.id, second.id


async def test_a_terminei_after_the_reading_ahead_asks_the_analyst_nothing_and_says_the_same(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        with monkeypatch.context() as cold:
            cold.setattr(bt_api, "read_ahead", _nothing_read_ahead, raising=False)
            cold_id, cold_stretch = await _a_second_stretch_after_the_first_terminei(
                client, db_session, analyst
            )
            cold_verdict = (await press_terminei(client, cold_id)).json()
            cold_brief = room.briefs[-1]

        session_id, stretch = await _a_second_stretch_after_the_first_terminei(
            client, db_session, analyst
        )
        read_before = analyst.whole_readings
        verdict = (await press_terminei(client, session_id)).json()

    assert analyst.whole_readings == read_before, (
        "o terminei lia de novo o que já tinha sido lido no último trecho"
    )
    assert verdict["finding_kind"] == "addition"
    assert verdict["finding_segment_id"] == stretch
    assert cold_verdict["finding_segment_id"] == cold_stretch
    same = ("checked", "finding_kind", "findings_remaining", "fixed_line", "used_fail_safe")
    assert {key: verdict[key] for key in same} == {key: cold_verdict[key] for key in same}
    assert room.briefs[-1] == cold_brief.replace(cold_id, session_id)


async def test_the_first_terminei_finds_the_reading_ready_and_the_listening_is_still_asked(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        analyst.readings = [AN_ADDITION]
        await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)
        read_by_the_stretch = analyst.whole_readings
        unheard = (await press_terminei(client, session.id)).json()
        verdict = (
            await press_terminei(client, session.id, report=played_every_part([part.id]))
        ).json()

    assert unheard["unheard_take_ids"] == [part.id], (
        "a leitura pronta fazia o terminei esquecer a parte que ninguém tinha ouvido"
    )
    assert read_by_the_stretch == 1, "o último trecho da primeira rodada não mandava ler"
    assert analyst.whole_readings == 1, (
        "o primeiro terminei lia de novo o que o último trecho já tinha mandado ler"
    )
    assert verdict["finding_kind"] == "addition"


async def test_a_stretch_told_while_a_part_is_still_untold_starts_no_reading(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        await another_rehearsal_take(
            db_session, session, sha256="b" * 64, scope="parte-2", ordinal=2, created_at=after(part)
        )
        await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)

    assert analyst.whole_readings == 1, (
        "o trecho mandava ler com uma parte gravada que ninguém tinha contado de volta"
    )


async def test_a_stretch_told_while_a_piece_of_another_is_still_untold_starts_no_reading(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        (stretch,) = await final_segments(db_session, session.id)
        await a_piece_still_to_be_told(db_session, session, stretch)
        await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)

    assert analyst.whole_readings == 1, (
        "o trecho mandava ler com um pedaço de trecho cortado ainda sem nada contado"
    )


async def test_a_stretch_told_after_the_reading_ahead_throws_it_away_and_terminei_reads_again(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        session_id, _ = await _a_second_stretch_after_the_first_terminei(
            client, db_session, analyst
        )
        (part,) = {stretch.take_id for stretch in await final_segments(db_session, session_id)}
        with monkeypatch.context() as unread:
            unread.setattr(bt_api, "read_ahead", _nothing_read_ahead)
            await _tell(
                client, session_id, await take_by_id(db_session, part), starts_ms=2000, ends_ms=3000
            )
        read_before = analyst.whole_readings
        verdict = (await press_terminei(client, session_id)).json()

    assert analyst.whole_readings == read_before + 1, (
        "o terminei servia a leitura de um conjunto que já não era o contado"
    )
    assert verdict["checked"] is True
    assert verdict["finding_kind"] is None


async def test_a_terminei_pressed_while_the_reading_ahead_runs_waits_for_it_instead_of_reading(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    reading = asyncio.Event()
    answer = asyncio.Event()
    scripted = analyst.__call__

    async def still_reading(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if analyst.readings:
            reading.set()
            await answer.wait()
        return await scripted(system_prompt=system_prompt, user_content=user_content)

    monkeypatch.setattr(bt_service, "call_agent", still_reading)

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        analyst.readings = [AN_ADDITION]
        told = asyncio.create_task(_tell(client, session.id, part, starts_ms=1000, ends_ms=2000))
        await asyncio.wait_for(reading.wait(), timeout=5)
        pressed = asyncio.create_task(press_terminei(client, session.id))
        await asyncio.sleep(0.05)
        answer.set()
        await asyncio.wait_for(told, timeout=5)
        verdict = (await asyncio.wait_for(pressed, timeout=5)).json()

    assert analyst.whole_readings == 2, (
        "o terminei lia de novo enquanto a leitura adiantada ainda estava em voo"
    )
    assert verdict["finding_kind"] == "addition"


async def test_the_reading_ahead_says_nothing_the_speaker_and_the_validator_wait_for_terminei(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        heard_by_then = (list(room.said), list(room.briefs), list(room.judged))
        analyst.readings = [AN_ADDITION]
        await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)

    assert analyst.whole_readings == 2
    assert (room.said, room.briefs, room.judged) == heard_by_then, (
        "a leitura adiantada fazia a sala falar antes do terminei"
    )


async def test_the_closing_reading_after_a_mended_stretch_is_the_one_read_ahead(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    raised = {"findings": [{"kind": "addition", "note": "Boaz não está nesta cena.", "chunk": 1}]}

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        analyst.readings = [raised]
        first = (
            await press_terminei(client, session.id, report=played_every_part([part.id]))
        ).json()
        await _tell(client, session.id, part, starts_ms=0, ends_ms=1000, again=True)
        read_before = analyst.whole_readings
        verdict = (await press_terminei(client, session.id)).json()

    assert first["finding_kind"] == "addition"
    assert len(analyst.verifications) == 1
    assert analyst.whole_readings == read_before, (
        "a leitura de fechamento era paga no terminei com a leitura adiantada já pronta"
    )
    assert verdict["checked"] is True


async def test_a_stretch_retold_over_its_own_slice_starts_the_reading_the_closing_one_uses(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    raised = {"findings": [{"kind": "addition", "note": "Boaz não está nesta cena.", "chunk": 1}]}

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        analyst.readings = [raised]
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        (stretch,) = await final_segments(db_session, session.id)
        await _tell_again(client, session.id, stretch)
        read_before = analyst.whole_readings
        verdict = (await press_terminei(client, session.id)).json()

    assert read_before == 2, "recontar o trecho não mandava ler o conjunto que ficou completo"
    assert len(analyst.verifications) == 1
    assert analyst.whole_readings == read_before, (
        "a leitura de fechamento era paga no terminei depois de recontar o trecho"
    )
    assert verdict["checked"] is True


async def test_a_stretch_retold_after_the_reading_ahead_throws_it_away_too(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        session_id, second = await _a_second_stretch_after_the_first_terminei(
            client, db_session, analyst
        )
        retold = next(
            stretch
            for stretch in await final_segments(db_session, session_id)
            if stretch.id == second
        )
        with monkeypatch.context() as unread:
            unread.setattr(segments_api, "read_ahead", _nothing_read_ahead)
            await _tell_again(client, session_id, retold)
        read_before = analyst.whole_readings
        verdict = (await press_terminei(client, session_id)).json()

    assert analyst.whole_readings == read_before + 1, (
        "o terminei servia a leitura de antes de o trecho ser recontado"
    )
    assert verdict["checked"] is True


async def test_a_stretch_told_while_an_older_reading_runs_calls_that_reading_off(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    reading = asyncio.Event()
    never = asyncio.Event()
    called_off: list[str] = []
    scripted = analyst.__call__

    async def outrun(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if not reading.is_set():
            reading.set()
            try:
                await never.wait()
            except asyncio.CancelledError:
                called_off.append(system_prompt)
                raise
        return await scripted(system_prompt=system_prompt, user_content=user_content)

    monkeypatch.setattr(bt_service, "call_agent", outrun)

    try:
        async with room_client(db_session, monkeypatch, per_request=per_request) as client:
            older = asyncio.create_task(
                _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)
            )
            await asyncio.wait_for(reading.wait(), timeout=5)
            analyst.readings = [AN_ADDITION]
            await _tell(client, session.id, part, starts_ms=2000, ends_ms=3000)
            await asyncio.wait_for(older, timeout=2)
            read_before = analyst.whole_readings
            verdict = (
                await press_terminei(client, session.id, report=played_every_part([part.id]))
            ).json()
    finally:
        never.set()

    assert len(called_off) == 1, "a leitura de um conjunto que já mudou seguia gastando"
    assert analyst.whole_readings == read_before
    assert verdict["finding_kind"] == "addition"


async def test_a_terminei_waiting_on_a_reading_that_is_called_off_reads_for_itself(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    reading = asyncio.Event()
    never = asyncio.Event()
    scripted = analyst.__call__

    async def outrun(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if not reading.is_set():
            reading.set()
            await never.wait()
        return await scripted(system_prompt=system_prompt, user_content=user_content)

    monkeypatch.setattr(bt_service, "call_agent", outrun)

    try:
        async with room_client(db_session, monkeypatch, per_request=per_request) as client:
            older = asyncio.create_task(
                _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)
            )
            await asyncio.wait_for(reading.wait(), timeout=5)
            pressed = asyncio.create_task(
                press_terminei(client, session.id, report=played_every_part([part.id]))
            )
            await asyncio.sleep(0.05)
            await _tell(client, session.id, part, starts_ms=2000, ends_ms=3000)
            await asyncio.wait_for(older, timeout=2)
            verdict = await asyncio.wait_for(pressed, timeout=2)
    finally:
        never.set()

    assert verdict.status_code == 200, "o terminei morria com a leitura que esperava cancelada"
    assert analyst.whole_readings == 2


class _Unreachable(Exception):
    pass


async def test_a_reading_ahead_that_fails_leaves_the_stretch_told_and_terminei_reads_as_before(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    scripted = analyst.__call__

    async def unreachable_ahead(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if analyst.readings:
            analyst.readings.clear()
            raise _Unreachable("o analista caiu")
        return await scripted(system_prompt=system_prompt, user_content=user_content)

    monkeypatch.setattr(bt_service, "call_agent", unreachable_ahead)

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        analyst.readings = [AN_ADDITION]
        told = await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)
        verdict = await press_terminei(client, session.id)

    assert told.json()["captured"] is True, "a queda da leitura adiantada derrubava o trecho"
    assert verdict.status_code == 200, verdict.text
    assert analyst.whole_readings == 2, "o terminei não lia por conta própria depois da queda"


async def test_a_terminei_waiting_on_a_reading_ahead_that_fails_reads_for_itself(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    analyst: Analyst,
    room: Room,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])
    reading = asyncio.Event()
    answer = asyncio.Event()
    scripted = analyst.__call__

    async def falls_while_reading(*, system_prompt: str, user_content: str, **_: Any) -> str:
        if analyst.readings:
            analyst.readings.clear()
            reading.set()
            await answer.wait()
            raise _Unreachable("o analista caiu no meio da leitura")
        return await scripted(system_prompt=system_prompt, user_content=user_content)

    monkeypatch.setattr(bt_service, "call_agent", falls_while_reading)

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        analyst.readings = [AN_ADDITION]
        told = asyncio.create_task(_tell(client, session.id, part, starts_ms=1000, ends_ms=2000))
        await asyncio.wait_for(reading.wait(), timeout=5)
        pressed = asyncio.create_task(press_terminei(client, session.id))
        await asyncio.sleep(0.05)
        answer.set()
        await asyncio.wait_for(told, timeout=5)
        verdict = await asyncio.wait_for(pressed, timeout=5)

    assert verdict.status_code == 200, verdict.text
    assert analyst.whole_readings == 2, "o terminei ficava com a queda da leitura que esperava"


class _Models:
    async def create(self, **kwargs: Any) -> SimpleNamespace:
        system = kwargs["system"]
        system = system if isinstance(system, str) else "".join(b["text"] for b in system)
        if kwargs["messages"][-1]["content"] == "Compare a tradução com o mapa.":
            text = '{"evidence_sufficient": true, "findings": []}'
        elif "corrected_response" in system:
            text = json.dumps({"verdict": "pass", "issues": []})
        else:
            text = "Vocês contaram bem."
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=10,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


@pytest.fixture()
def models(monkeypatch: pytest.MonkeyPatch):
    async def voice(text: str, *_: Any, **__: Any) -> tuple[Any, bool]:
        return type("Voiced", (), {"key": "clipe-1"})(), False

    llm._SETTLED.clear()
    usage.forget_sessions()
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-ant-fake", raising=False)
    monkeypatch.setattr(
        llm.anthropic, "AsyncAnthropic", lambda **_: SimpleNamespace(messages=_Models())
    )
    monkeypatch.setattr(bt_api.room, "synthesize_facilitator_speech", voice)
    yield
    llm._SETTLED.clear()
    usage.forget_sessions()


async def test_the_reading_ahead_is_the_sessions_money_and_adds_no_turn(
    db_session: AsyncSession,
    per_request: async_sessionmaker[AsyncSession],
    models: None,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session, (part,) = await rehearsed_in_parts_of(db_session, [1])

    async with room_client(db_session, monkeypatch, per_request=per_request) as client:
        await press_terminei(client, session.id, report=played_every_part([part.id]))
        with caplog.at_level(logging.INFO):
            await _tell(client, session.id, part, starts_ms=1000, ends_ms=2000)

    lines = [
        record
        for record in caplog.records
        if getattr(record, "session_turns", None) is not None
        and getattr(record, "session_id", None) == session.id
    ]
    assert [(line.session_turns, line.session_calls) for line in lines] == [(1, 3)], (
        "a leitura adiantada rodava fora de qualquer total da sessão"
    )


class _NoConnection:
    async def __aenter__(self) -> AsyncSession:
        raise TimeoutError("the pool had no connection to give")

    async def __aexit__(self, *_: object) -> bool:
        return False


async def test_a_reading_ahead_that_cannot_reach_the_database_is_logged_and_dropped(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    from app.services.internalization_room import background

    monkeypatch.setattr(background, "AsyncSessionLocal", _NoConnection)

    with caplog.at_level(logging.ERROR, logger=background.__name__):
        await background.read_ahead(session_id="a-session-the-stretch-already-answered")

    assert "Reading ahead failed for session a-session-the-stretch-already-answered" in caplog.text
