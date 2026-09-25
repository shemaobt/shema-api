import asyncio
import json
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import UpstreamServiceError
from app.core.room_enums import CoverageStatus, HaltKind
from app.db.models.internalization_room import IRSession, IRSessionStatus, IRTurn
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.hearing import HeardSpeech
from app.services.internalization_room.sessions import (
    append_exchange,
    apply_coverage,
    attend,
    create_session,
    get_session,
    mark_needs_person,
    save_comprehension,
    unattend,
)
from app.services.platform.tts import SynthesizedSpeech, Upload
from tests.baker import fully_supported_comprehension
from tests.release_harness import KEY, PREFIX, a_claimed_device, team_headers
from tests.room_harness import counting_commits, room_client

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
    with counting_commits(test_engine) as counted:
        yield counted


async def _the_team_answers(
    client: httpx.AsyncClient, session_id: str, **data: str
) -> httpx.Response:
    return await client.post(
        f"{PREFIX}/sessions/{session_id}/turns",
        headers={"X-Room-Key": KEY},
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
        data=data,
    )


def _in_a_transaction_while_thinking(
    monkeypatch: pytest.MonkeyPatch, db: AsyncSession, models: _Models, voice: _Voice
) -> dict[str, bool]:
    from app.api.internalization_room import sessions as sessions_api
    from app.services.internalization_room import turn_dedup

    held: dict[str, bool] = {}
    of_their_own: list[AsyncSession] = []
    opens = turn_dedup.AsyncSessionLocal

    def a_session_of_its_own() -> AsyncSession:
        of_their_own.append(opens())
        return of_their_own[-1]

    def in_a_transaction() -> bool:
        return any(each.in_transaction() for each in (db, *of_their_own))

    async def heard(audio: bytes, **kwargs: Any) -> HeardSpeech:
        held["stt"] = in_a_transaction()
        return await _heard(audio, **kwargs)

    async def thinks(*, system_prompt: str, **kwargs: Any) -> str:
        role = "validator" if "corrected_response" in system_prompt else "guide"
        held[role] = in_a_transaction()
        return await models(system_prompt=system_prompt, **kwargs)

    async def speaks(text: str, **kwargs: Any) -> tuple[SynthesizedSpeech, bool]:
        held["voice"] = in_a_transaction()
        return await voice(text, **kwargs)

    monkeypatch.setattr(turn_dedup, "AsyncSessionLocal", a_session_of_its_own)
    monkeypatch.setattr(sessions_api, "heard_speech", heard)
    monkeypatch.setattr(
        sys.modules["app.services.internalization_room.run_turn"], "call_agent", thinks
    )
    monkeypatch.setattr(sessions_api.room, "synthesize_facilitator_speech", speaks)
    return held


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


async def test_a_person_asked_for_while_the_guide_composes_the_opening_is_still_asked_for(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    async def the_tablet_asks_for_a_person() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, session.id)
            await mark_needs_person(rival, halted, kind=HaltKind.BLOCKING)

    models.while_the_guide_thinks = the_tablet_asks_for_a_person

    opened = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:300]
    assert models.while_the_guide_thinks is None, "o Guia falso não compôs a abertura"
    async with rival_factory() as fresh:
        after = await get_session(fresh, session.id)
    assert after.messages, "a abertura não foi gravada"
    assert after.status is IRSessionStatus.NEEDS_PERSON, (
        "a releitura da abertura pegava o pedido de pessoa e a primeira fala o soltava"
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


async def test_the_models_think_with_the_database_let_go_not_with_the_read_still_open(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    voice: _Voice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held = _in_a_transaction_while_thinking(monkeypatch, db_session, models, voice)

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    assert held == {"stt": False, "guide": False, "validator": False, "voice": False}, (
        "a leitura da sessão abria a transação e a conexão ficava presa pelo STT, pelo Guia,"
        " pelo Validador e pela voz"
    )


async def test_a_tablets_turn_with_an_id_lets_go_of_the_read_its_credential_opened(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    models: _Models,
    voice: _Voice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project, credential = await a_claimed_device(db_session)
    session = await create_session(db_session, language="pt", pericope=P, project_id=project.id)
    await append_exchange(db_session, session, team_utterance="", guide_response=FIRST_QUESTION)
    held = _in_a_transaction_while_thinking(monkeypatch, db_session, models, voice)

    answered = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers=team_headers(credential),
        files={"file": ("answer.m4a", b"audio", "audio/m4a")},
        data={"turn_id": "turno-1"},
    )

    assert answered.status_code == 200, answered.text[:300]
    assert held == {"stt": False, "guide": False, "validator": False, "voice": False}, (
        "a credencial lia o aparelho na sessão do pedido, o turno corria noutra, e a do pedido"
        " ficava presa na transação até o fim"
    )


async def test_a_turn_whose_row_moved_while_the_guide_thought_is_refused_not_written_over(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def another_turn_lands_first() -> None:
        async with rival_factory() as rival:
            other = await get_session(rival, waiting_room.id)
            await append_exchange(
                rival, other, team_utterance="Rute ficou", guide_response="E depois?"
            )

    models.while_the_guide_thinks = another_turn_lands_first

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 409, answered.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert [m["text"] for m in after.messages] == [FIRST_QUESTION, "Rute ficou", "E depois?"], (
        "com a transação solta antes do Guia, o turno escrevia por cima da troca que chegou antes"
    )


async def test_an_opening_the_room_voices_live_is_composed_with_the_database_let_go(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    models: _Models,
    voice: _Voice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    held = _in_a_transaction_while_thinking(monkeypatch, db_session, models, voice)

    opened = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:300]
    assert held == {"guide": False, "validator": False, "voice": False}, (
        "a abertura ao vivo compunha e falava com a leitura da sessão ainda aberta"
    )


async def test_a_line_said_again_is_voiced_with_the_database_let_go(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    voice: _Voice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    held = _in_a_transaction_while_thinking(monkeypatch, db_session, models, voice)

    again = await client.post(
        f"{PREFIX}/sessions/{waiting_room.id}/turns", headers={"X-Room-Key": KEY}
    )

    assert again.status_code == 200, again.text[:300]
    assert held == {"voice": False}, (
        "o diga-de-novo sintetizava a última fala com a leitura da sessão ainda aberta"
    )


async def test_an_opening_the_tablet_names_is_composed_with_every_session_let_go(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    models: _Models,
    voice: _Voice,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)
    held = _in_a_transaction_while_thinking(monkeypatch, db_session, models, voice)

    opened = await client.post(
        f"{PREFIX}/sessions/{session.id}/turns",
        headers={"X-Room-Key": KEY},
        data={"turn_id": "abertura-1"},
    )

    assert opened.status_code == 200, opened.text[:300]
    assert held == {"guide": False, "validator": False, "voice": False}, (
        "a abertura com turn_id corria numa sessão própria que ninguém olhava, com a leitura"
        " ainda aberta nela"
    )


async def test_a_halt_the_tablet_raises_while_the_guide_answers_a_halted_room_stays_standing(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    await mark_needs_person(db_session, waiting_room, kind=HaltKind.WARNING)

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
        "o turno que começou parado soltava também o pedido que o tablet fez durante o Guia"
    )
    assert after.halt_kind == HaltKind.BLOCKING.value


async def test_a_warning_raised_again_after_a_visit_while_the_guide_answers_is_not_lifted(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    await mark_needs_person(db_session, waiting_room, kind=HaltKind.WARNING)

    async def a_visit_and_then_the_room_asks_again() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, waiting_room.id)
            await attend(rival, halted, by="facilitadora")
            await mark_needs_person(rival, halted, kind=HaltKind.WARNING)

    models.while_the_guide_thinks = a_visit_and_then_the_room_asks_again

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert after.status is IRSessionStatus.NEEDS_PERSON, (
        "o turno tomava o segundo aviso, levantado depois da visita, pelo aviso em que começou,"
        " e soltava um pedido que ninguém tinha atendido"
    )
    assert after.halt_kind == HaltKind.WARNING.value


async def test_a_passage_the_settle_closes_while_the_guide_answers_a_halted_room_stays_closed(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    await save_comprehension(db_session, waiting_room, fully_supported_comprehension(P))
    await mark_needs_person(db_session, waiting_room, kind=HaltKind.BLOCKING)

    async def a_visit_and_then_the_last_settle_close_the_passage() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, waiting_room.id)
            await attend(rival, halted, by="facilitadora")
            await apply_coverage(
                rival,
                waiting_room.id,
                dict.fromkeys(initial_state(P), CoverageStatus.ENGAGED.value),
            )

    models.while_the_guide_thinks = a_visit_and_then_the_last_settle_close_the_passage

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        after = await get_session(fresh, waiting_room.id)
    assert after.status is IRSessionStatus.DONE, (
        "o turno que começou parado reabria como em curso a passagem que o settle fechou"
        " durante o Guia, com o ended_at ainda carimbado"
    )


async def test_undoing_a_visit_to_a_halt_raised_while_the_guide_answered_puts_the_halt_back(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def the_tablet_asks_and_a_facilitator_marks_the_visit() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, waiting_room.id)
            await mark_needs_person(rival, halted, kind=HaltKind.BLOCKING)
            await attend(rival, halted, by="facilitadora")

    models.while_the_guide_thinks = the_tablet_asks_and_a_facilitator_marks_the_visit

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        undone = await unattend(fresh, await get_session(fresh, waiting_room.id))
    assert undone.status is IRSessionStatus.NEEDS_PERSON, (
        "o turno apagava o lifted_halt de uma parada que nem existia quando começou, e"
        " desfazer a visita não trazia o pedido de volta"
    )
    assert undone.halt_kind == HaltKind.BLOCKING.value


async def test_undoing_a_visit_to_the_halt_the_turn_began_in_does_not_stop_the_team_again(
    client: httpx.AsyncClient,
    waiting_room: IRSession,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    await mark_needs_person(db_session, waiting_room, kind=HaltKind.BLOCKING)

    async def a_facilitator_marks_the_visit() -> None:
        async with rival_factory() as rival:
            await attend(rival, await get_session(rival, waiting_room.id), by="facilitadora")

    models.while_the_guide_thinks = a_facilitator_marks_the_visit

    answered = await _the_team_answers(client, waiting_room.id)

    assert answered.status_code == 200, answered.text[:300]
    async with rival_factory() as fresh:
        undone = await unattend(fresh, await get_session(fresh, waiting_room.id))
    assert undone.status is IRSessionStatus.IN_PROGRESS, (
        "o turno teria soltado essa parada com ou sem a visita, e desfazer a visita parava"
        " a conversa que a equipe já tinha retomado"
    )


async def test_undoing_a_visit_to_a_halt_raised_while_the_opening_was_composed_puts_it_back(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    models: _Models,
    rival_factory: async_sessionmaker[AsyncSession],
) -> None:
    session = await create_session(db_session, language="pt", pericope=P)

    async def the_tablet_asks_and_a_facilitator_marks_the_visit() -> None:
        async with rival_factory() as rival:
            halted = await get_session(rival, session.id)
            await mark_needs_person(rival, halted, kind=HaltKind.BLOCKING)
            await attend(rival, halted, by="facilitadora")

    models.while_the_guide_thinks = the_tablet_asks_and_a_facilitator_marks_the_visit

    opened = await client.post(f"{PREFIX}/sessions/{session.id}/turns", headers={"X-Room-Key": KEY})

    assert opened.status_code == 200, opened.text[:300]
    assert models.while_the_guide_thinks is None, "o Guia falso não compôs a abertura"
    async with rival_factory() as fresh:
        undone = await unattend(fresh, await get_session(fresh, session.id))
    assert undone.messages, "a abertura não foi gravada"
    assert undone.status is IRSessionStatus.NEEDS_PERSON, (
        "a abertura relia a visita junto com as mensagens, tomava-a por anterior ao Guia"
        " e apagava o que desfazê-la traria de volta"
    )
