import asyncio
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.database import engine as app_engine
from app.core.exceptions import UpstreamServiceError
from app.core.room_enums import CoverageStatus, HaltKind
from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTurn
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    create_session,
    get_session,
    mark_needs_person,
)
from app.services.platform.tts import SynthesizedSpeech, Upload
from tests.release_harness import KEY, PREFIX
from tests.room_harness import room_client

P = "P03"
FIRST_QUESTION = "Quem aparece nesta parte?"
GUIDE_LINE = "Vamos ficar nesta cena. O que vocês contariam?"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"


class _Models:
    def __init__(self) -> None:
        self.while_the_guide_thinks: Callable[[], Awaitable[None]] | None = None

    async def __call__(self, *, system_prompt: str, **_: Any) -> str:
        if "corrected_response" in system_prompt:
            return json.dumps({"verdict": "pass", "issues": []})
        if self.while_the_guide_thinks is not None:
            elsewhere, self.while_the_guide_thinks = self.while_the_guide_thinks, None
            await elsewhere()
        return GUIDE_LINE


@pytest.fixture()
def models() -> _Models:
    return _Models()


@pytest.fixture()
def rival_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(test_engine, expire_on_commit=False, class_=AsyncSession)


class _Voice:
    def __init__(self) -> None:
        self.the_bucket_is_down = False
        self.written = asyncio.Event()

    async def _the_bucket_refuses_once_the_turn_is_written(self) -> None:
        await asyncio.wait_for(self.written.wait(), timeout=1)
        raise UpstreamServiceError("the bucket is down")

    async def __call__(
        self, text: str, *, uploads: list[Upload] | None = None, **_: Any
    ) -> tuple[SynthesizedSpeech, bool]:
        if self.the_bucket_is_down and uploads is not None:
            self.the_bucket_is_down = False
            uploads.append(self._the_bucket_refuses_once_the_turn_is_written)
        entry = SynthesizedSpeech(
            audio=b"audio",
            mime_type="audio/mpeg",
            etag="e",
            cached=False,
            key=f"tts/voice/m/f/{len(text)}.mp3",
        )
        return entry, False


@pytest.fixture()
def voice() -> _Voice:
    return _Voice()


async def _heard(audio: bytes, **_: Any) -> HeardSpeech:
    return HeardSpeech(text=TEAM_ANSWER)


async def _settled_later(**_: Any) -> None:
    return None


@pytest.fixture()
async def client(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, models: _Models, voice: _Voice
) -> AsyncIterator[httpx.AsyncClient]:
    from app.api.internalization_room import sessions as sessions_api

    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", models
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", voice)
    monkeypatch.setattr(sessions_api, "heard_speech", _heard)
    monkeypatch.setattr(sessions_api, "settle_coverage", _settled_later)
    async with room_client(db_session, monkeypatch) as c:
        yield c


@pytest.fixture()
async def waiting_room(db_session: AsyncSession) -> IRSession:
    session = await create_session(db_session, language="pt", pericope=P)
    return await append_exchange(
        db_session, session, team_utterance="", guide_response=FIRST_QUESTION
    )


@pytest.fixture()
def commits(test_engine) -> Iterator[list[object]]:
    counted: list[object] = []

    def _count(connection: object) -> None:
        counted.append(connection)

    engines = (test_engine.sync_engine, app_engine.sync_engine)
    for each in engines:
        event.listen(each, "commit", _count)
    try:
        yield counted
    finally:
        for each in engines:
            event.remove(each, "commit", _count)


async def _the_team_answers(
    client: httpx.AsyncClient, session_id: str, **data: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
        data=data,
    )


async def test_a_voiced_turn_reaches_the_database_in_one_commit_not_two(
    client: httpx.AsyncClient, waiting_room: IRSession, commits: list[object]
) -> None:
    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    assert len(commits) == 1, (
        "o turno gravava a comprehension e as mensagens em dois commits, cada um com o seu"
        " refresh da linha inteira"
    )


async def test_an_opening_the_room_voices_live_reaches_the_database_in_one_commit(
    client: httpx.AsyncClient, db_session: AsyncSession, commits: list[object]
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    commits.clear()

    opened = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:300]
    assert len(commits) == 1, "a abertura gravava a comprehension e a primeira fala em dois commits"


async def test_a_bead_settled_while_the_guide_thinks_is_lit_in_the_turns_answer(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    lit = dict(initial_state(P))
    lit[next(iter(lit))] = CoverageStatus.ENGAGED.value

    async def the_last_turns_settle_lands() -> None:
        async with rival_factory() as rival:
            await apply_coverage(rival, waiting_room.id, lit)

    models.while_the_guide_thinks = the_last_turns_settle_lands

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    assert answered.json()["coverage"]["engaged"] == 1, (
        "a resposta levava as contas lidas antes do Guia, e a conta acesa apagava na tela"
    )


async def test_a_person_asked_for_while_the_guide_thinks_is_still_asked_for_after_the_turn(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def the_tablet_asks_for_a_person() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, waiting_room.id)
            await mark_needs_person(rival, halted, kind=HaltKind.BLOCKING)

    models.while_the_guide_thinks = the_tablet_asks_for_a_person

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert after.status is IRSessionStatus.NEEDS_PERSON, (
        "o turno relia o status depois do primeiro commit e soltava o pedido de pessoa"
    )
    assert after.halt_kind == HaltKind.BLOCKING.value


async def test_a_turn_with_its_id_is_remembered_in_the_same_commit_as_its_exchange(
    client: httpx.AsyncClient, waiting_room: IRSession, commits: list[object]
) -> None:
    answered = await _the_team_answers(client, waiting_room.id, turn_id="turno-1")

    assert answered.status_code == 200, answered.text[:300]
    assert len(commits) == 1, "a resposta lembrada do turno era gravada num commit a mais"


async def test_a_resend_remembered_while_the_guide_thinks_does_not_undo_the_exchange(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def a_resend_is_answered_first() -> None:
        async with rival_factory() as rival:
            rival.add(IRTurn(session_id=waiting_room.id, turn_id="turno-1", response={}))
            await rival.commit()

    models.while_the_guide_thinks = a_resend_is_answered_first

    answered = await _the_team_answers(client, waiting_room.id, turn_id="turno-1")

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert [m["text"] for m in after.messages if m["role"] == "guide"] == [
        FIRST_QUESTION,
        GUIDE_LINE,
    ], "a resposta lembrada em duplicata voltava a transação e levava a troca junto"


async def test_a_turn_whose_clip_never_reached_the_bucket_is_not_written_and_its_resend_is(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    voice: _Voice,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.internalization_room import sessions as sessions_api

    append = sessions_api.room.append_exchange

    async def append_then_say_so(*args: Any, **kwargs: Any) -> IRSession:
        appended = await append(*args, **kwargs)
        voice.written.set()
        return appended

    monkeypatch.setattr(sessions_api.room, "append_exchange", append_then_say_so)
    voice.the_bucket_is_down = True

    failed = await _the_team_answers(client, waiting_room.id, turn_id="turno-1")

    assert failed.status_code >= 500, failed.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
        remembered = (await fresh.execute(select(IRTurn))).scalars().all()
    assert [m["text"] for m in after.messages if m["role"] == "guide"] == [FIRST_QUESTION], (
        "a troca ficava gravada sem a equipe ter ouvido nada"
    )
    assert remembered == []

    resent = await _the_team_answers(client, waiting_room.id, turn_id="turno-1")

    assert resent.status_code == 200, resent.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert [m["text"] for m in after.messages if m["role"] == "guide"] == [
        FIRST_QUESTION,
        GUIDE_LINE,
    ], "o reenvio repetia o turno e gravava a troca duas vezes"
