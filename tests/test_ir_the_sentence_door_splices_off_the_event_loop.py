"""The sentence door works the audio on a worker thread and keeps the session row lock short.

Parsing, trimming and splicing a part is pure Python over up to 4 MB plus the whole part; run on
the event loop it stalled every other request of the worker, and run under the session row lock it
held every other writer of the session as well (ENG-1221's findings, ENG-1688).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRSegment, IRTake, IRTakeKind
from app.services.internalization_room import sentences
from app.services.internalization_room.sentences import lay_in_a_sentence
from app.services.internalization_room.sessions import back_translation_of, get_session
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
from tests.sentence_harness import (
    PART,
    Speaker,
    laid_in_and_told_again,
    named_and_heard,
    nuance_of_frase,
    re_record,
    rehearsed_in_wav,
    samples_of,
    spoken,
    take_named,
)
from tests.turn_harness import the_room_agent_is


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
async def client(
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    store: MemoryStore,
):
    async with room_client(db_session, monkeypatch, per_request=rival_factory) as door:
        yield door


class SessionLock:
    def __init__(self) -> None:
        self.held = False


def watching_the_session_lock(monkeypatch: pytest.MonkeyPatch) -> SessionLock:
    lock = SessionLock()
    execute, commit, rollback = AsyncSession.execute, AsyncSession.commit, AsyncSession.rollback

    async def locking(self: AsyncSession, statement: Any, *args: Any, **kwargs: Any) -> Any:
        if getattr(statement, "_for_update_arg", None) is not None:
            lock.held = True
        return await execute(self, statement, *args, **kwargs)

    async def committing(self: AsyncSession) -> None:
        await commit(self)
        lock.held = False

    async def rolling_back(self: AsyncSession) -> None:
        await rollback(self)
        lock.held = False

    monkeypatch.setattr(AsyncSession, "execute", locking)
    monkeypatch.setattr(AsyncSession, "commit", committing)
    monkeypatch.setattr(AsyncSession, "rollback", rolling_back)
    return lock


def noting_the_thread(
    ran_on: dict[str, set[int]], name: str, original: Callable[..., Any]
) -> Callable[..., Any]:
    def noted(*args: Any, **kwargs: Any) -> Any:
        ran_on.setdefault(name, set()).add(threading.get_ident())
        return original(*args, **kwargs)

    return noted


async def test_the_part_is_parsed_trimmed_and_spliced_off_the_event_loop(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    ran_on: dict[str, set[int]] = {}
    for name in ("pcm16", "trim_silence", "splice_sentence"):
        monkeypatch.setattr(
            sentences, name, noting_the_thread(ran_on, name, getattr(sentences, name))
        )
    event_loop_thread = threading.get_ident()

    laid = await re_record(client, session.id, frase.id, spoken(1.0))

    assert laid.status_code == 200, laid.text
    assert set(ran_on) == {"pcm16", "trim_silence", "splice_sentence"}
    assert all(event_loop_thread not in threads for threads in ran_on.values()), (
        "a emenda de uma parte inteira rodava na thread do loop, e o worker parava com ela"
    )


async def test_the_session_row_lock_is_let_go_while_the_part_is_spliced(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    lock = watching_the_session_lock(monkeypatch)
    held_while_splicing: list[bool] = []
    splice = sentences.splice_sentence

    def splicing(*args: Any, **kwargs: Any) -> Any:
        held_while_splicing.append(lock.held)
        return splice(*args, **kwargs)

    monkeypatch.setattr(sentences, "splice_sentence", splicing)

    laid = await re_record(client, session.id, frase.id, spoken(1.0))

    assert laid.status_code == 200, laid.text
    assert held_while_splicing == [False], (
        "a linha da sessão ficava travada enquanto a parte era emendada, e todo outro pedido "
        "da sessão esperava por ela"
    )


async def test_a_frase_awaiting_its_translation_is_refused_before_the_parts_bytes_are_read(
    client: httpx.AsyncClient, db_session: AsyncSession, store: MemoryStore
) -> None:
    session, (_, unreadable), ((awaiting, _), (other,)) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)], [(0, 2000)]]
    )
    await re_record(client, session.id, awaiting.id, spoken(1.0), sentence_id="sentence-0001")
    store.objects[unreadable.storage_key] = b"isto nao e um wav"

    refused = await re_record(
        client, session.id, other.id, spoken(1.0), sentence_id="sentence-0002"
    )

    assert (refused.status_code, refused.json().get("code")) == (
        409,
        "ANOTHER_SENTENCE_AWAITS",
    ), "uma parte ilegível escondia que outra frase ainda esperava pela tradução"


async def test_a_sentence_laid_in_and_told_while_another_is_spliced_is_not_lost_under_it(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((first, middle, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000), (2000, 3000)]]
    )
    read = store.get
    rival_has_landed: list[bool] = []

    async def read_then_a_rival_lays_in_and_is_told(key: str) -> bytes | None:
        held = await read(key)
        if not rival_has_landed:
            rival_has_landed.append(True)
            await laid_in_and_told_again(client, session.id, middle.id, 1)
        return held

    monkeypatch.setattr(store, "get", read_then_a_rival_lays_in_and_is_told)

    laid = await re_record(client, session.id, first.id, spoken(0.5), sentence_id="sentence-0002")

    assert laid.status_code == 200, laid.text
    spans = [(one["starts_ms"], one["ends_ms"]) for one in laid.json()["segments"]]
    assert spans == [(0, 900), (900, 2300), (2300, 3300)]
    final = await take_named(db_session, laid.json()["segments"][0]["take_id"])
    assert len(samples_of(store.objects[final.storage_key])) == 52800, (
        "a frase emendada na parte lida antes da outra perdia a frase que entrou nesse meio tempo"
    )


async def test_the_same_sentence_sent_twice_at_once_is_laid_in_once(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((frase, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    read = store.get
    resent: list[bool] = []

    async def read_then_the_resend_lands(key: str) -> bytes | None:
        held = await read(key)
        if not resent:
            resent.append(True)
            async with rival_factory() as rival_db:
                await lay_in_a_sentence(
                    rival_db,
                    await get_session(rival_db, session.id),
                    await rival_db.get(IRSegment, frase.id),
                    sentence_id="sentence-0001",
                    audio=spoken(1.0),
                    device_id="tablet-da-equipe",
                    store=store,
                )
        return held

    monkeypatch.setattr(store, "get", read_then_the_resend_lands)

    laid = await re_record(client, session.id, frase.id, spoken(1.0), sentence_id="sentence-0001")

    assert laid.status_code == 200, laid.text
    async with rival_factory() as reading_db:
        stored = back_translation_of(await get_session(reading_db, session.id))
        rehearsals = await reading_db.scalar(
            select(func.count())
            .select_from(IRTake)
            .where(IRTake.session_id == session.id, IRTake.kind == IRTakeKind.ENSAIO)
        )
    assert [one.sentence_id for one in stored.sentences] == ["sentence-0001"], (
        "o reenvio que chegou durante a emenda era emendado de novo"
    )
    assert rehearsals == 2, "o reenvio deixava uma parte emendada a mais"


async def test_a_frase_told_again_while_its_sentence_is_spliced_takes_no_sentence(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,), ((frase, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    read = store.get
    told_again: list[bool] = []

    async def read_then_the_frase_is_told_again(key: str) -> bytes | None:
        held = await read(key)
        if not told_again:
            told_again.append(True)
            told = await client.post(
                f"{PREFIX}/sessions/{session.id}/segments/{frase.id}/replace",
                data={"take_id": part.id, "starts_ms": "0", "ends_ms": "1000"},
                files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
            )
            assert told.status_code == 200, told.text
        return held

    monkeypatch.setattr(store, "get", read_then_the_frase_is_told_again)

    refused = await re_record(client, session.id, frase.id, spoken(1.0))

    assert (refused.status_code, refused.json().get("code")) == (
        400,
        "STRETCH_NO_LONGER_COUNTS",
    ), "a frase contada de novo durante a emenda recebia a frase velha"
    assert [
        one.sentence_id
        for one in back_translation_of(await get_session(db_session, session.id)).sentences
    ] == []


async def test_a_nuance_heard_named_stays_named_through_a_lay_in_that_is_spliced_again(
    client: httpx.AsyncClient,
    analyst: Any,
    speaker: Speaker,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, (part,), (told,) = await rehearsed_in_wav(db_session, store, [PART])
    await named_and_heard(client, analyst, speaker, session.id, part.id, nuance_of_frase(3))
    read = store.get
    rival_has_landed: list[bool] = []

    async def read_then_a_rival_lays_in_and_is_told(key: str) -> bytes | None:
        held = await read(key)
        if not rival_has_landed:
            rival_has_landed.append(True)
            await laid_in_and_told_again(client, session.id, told[1].id, 1)
        return held

    monkeypatch.setattr(store, "get", read_then_a_rival_lays_in_and_is_told)
    laid = await re_record(client, session.id, told[0].id, spoken(0.5), sentence_id="sentence-0002")
    assert laid.status_code == 200, laid.text
    new = laid.json()["segments"][0]
    told_again = await client.post(
        f"{PREFIX}/sessions/{session.id}/segments/{told[0].id}/replace",
        data={
            "take_id": new["take_id"],
            "starts_ms": str(new["starts_ms"]),
            "ends_ms": str(new["ends_ms"]),
        },
        files={"file": ("trecho.m4a", b"a equipe traduziu a frase nova", "audio/mp4")},
    )
    assert told_again.status_code == 200, told_again.text
    analyst.readings = [{"findings": [nuance_of_frase(3)]}]
    speaker.line = "Vocês contaram bem."

    again = await press_terminei(
        client, session.id, report=played_every_part([new["take_id"]], duration_ms=3300)
    )

    assert again.status_code == 200, again.text
    assert speaker.handed() == [], (
        "a nuance dita sobre a terceira frase era nomeada de novo depois de duas frases "
        "regravadas, uma delas emendada outra vez"
    )
    async with rival_factory() as reading_db:
        kept = (await stored_telling_back(reading_db, session)).checks
    assert [one.voiced for one in kept[-1].nuances] == ["before"]
