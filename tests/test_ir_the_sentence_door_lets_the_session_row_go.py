"""The sentence door holds the session's row only around its writes, never across the bucket.

It splices, uploads both recordings and measures with nothing held, then takes the session's row
to check again and write. A sentence whose part changed meanwhile is refused `PART_CHANGED`, with
nothing written (ENG-1754, ADR 0089). On SQLite the row lock is the harness's stand-in for
Postgres', so a turn behind it waits as it would in production.
"""

from __future__ import annotations

import ast
import asyncio
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room import segments as segments_api
from app.db.models.internalization_room import IRTake, IRTakeKind
from app.services.internalization_room import sentences
from app.services.internalization_room.segments import final_segments
from app.services.internalization_room.sessions import (
    append_opening,
    back_translation_of,
    get_session,
)
from tests.hard_stretch_harness import MemoryStore
from tests.room_harness import nothing_is_read_ahead, room_client, the_bucket_is_in_memory
from tests.sentence_harness import (
    laid_in_and_told_again,
    re_record,
    rehearsed_in_wav,
    samples_of,
    spoken,
    take_named,
)
from tests.session_row_lock_harness import the_session_row_locks_as_postgres_does
from tests.turn_claim_harness import OPENING, Guide, a_voice, speak, the_guide_is

APP = Path(__file__).resolve().parent.parent / "app"
THE_SENTENCE_DOOR = "app/services/internalization_room/sentences.py"
#: The open of the Checagem externa takes the row around a read and an insert, with no bucket.
THE_EXTERNAL_CHECK_OPEN = "app/services/internalization_room/external_check.py"
THREE_FRASES = [[(0, 1000), (1000, 2000), (2000, 3000)]]
THE_BUCKET = ("get", "put", "stat")


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
async def client(
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    store: MemoryStore,
):
    async with room_client(db_session, monkeypatch, per_request=rival_factory) as door:
        yield door


def the_bucket_takes(
    monkeypatch: pytest.MonkeyPatch, store: MemoryStore, seconds: float, *names: str
) -> asyncio.Event:
    started = asyncio.Event()
    for name in names:
        original = getattr(store, name)

        async def slow(*args: Any, _original: Any = original, **kwargs: Any) -> Any:
            started.set()
            await asyncio.sleep(seconds)
            return await _original(*args, **kwargs)

        monkeypatch.setattr(store, name, slow)
    return started


class Rival:
    """A sentence another tablet lays into the middle frase and tells again, once, from inside
    the bucket call it is hooked on."""

    def __init__(self, client: httpx.AsyncClient, session_id: str, middle: str):
        self.client, self.session_id, self.middle = client, session_id, middle
        self.started = False
        self.take_id: str | None = None

    async def lands(self) -> None:
        if self.started:
            return
        self.started = True
        self.take_id = await laid_in_and_told_again(self.client, self.session_id, self.middle, 1)

    def after_the_part_is_read(self, monkeypatch: pytest.MonkeyPatch, store: MemoryStore) -> None:
        get = store.get

        async def read_then_the_rival(*args: Any, **kwargs: Any) -> Any:
            held = await get(*args, **kwargs)
            await self.lands()
            return held

        monkeypatch.setattr(store, "get", read_then_the_rival)

    def before_a_recording_is_uploaded(
        self, monkeypatch: pytest.MonkeyPatch, store: MemoryStore
    ) -> None:
        put = store.put

        async def the_rival_then_upload(*args: Any, **kwargs: Any) -> Any:
            await self.lands()
            return await put(*args, **kwargs)

        monkeypatch.setattr(store, "put", the_rival_then_upload)


async def _refused_while_a_rival_lands(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
    hooked: Callable[[Rival, pytest.MonkeyPatch, MemoryStore], None],
) -> tuple[Any, Any, Rival, httpx.Response]:
    session, _, ((first, middle, _),) = await rehearsed_in_wav(db_session, store, THREE_FRASES)
    rival = Rival(client, session.id, middle.id)
    hooked(rival, monkeypatch, store)
    refused = await re_record(
        client, session.id, first.id, spoken(0.5), sentence_id="sentence-0002"
    )
    return session, first, rival, refused


async def _nothing_of_the_refused_sentence_is_written(
    rival_factory: async_sessionmaker[AsyncSession], session_id: str, rival: Rival
) -> None:
    async with rival_factory() as reading_db:
        state = back_translation_of(await get_session(reading_db, session_id))
        frases = await final_segments(reading_db, session_id)
        rehearsals = await reading_db.scalar(
            select(func.count())
            .select_from(IRTake)
            .where(IRTake.session_id == session_id, IRTake.kind == IRTakeKind.ENSAIO)
        )
    assert [one.sentence_id for one in state.sentences] == ["sentence-0001"]
    assert (frases[0].starts_ms, frases[0].ends_ms) == (0, 1000)
    assert {one.take_id for one in frases} == {rival.take_id}, (
        "a frase recusada escrevia por cima da parte que o outro tablet acabara de emendar"
    )
    assert rehearsals == 2, "a frase recusada deixava uma parte emendada a mais"


async def test_a_turn_sent_while_the_bucket_takes_three_seconds_lands_in_under_a_second(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((frase, _),) = await rehearsed_in_wav(
        db_session, store, [[(0, 1000), (1000, 2000)]]
    )
    await append_opening(db_session, session, guide_response=OPENING)
    a_voice(monkeypatch)
    the_guide_is(monkeypatch, Guide()).first_takes = 0
    the_session_row_locks_as_postgres_does(monkeypatch)
    uploading = the_bucket_takes(monkeypatch, store, 3.0, "put")

    laying_in = asyncio.create_task(re_record(client, session.id, frase.id, spoken(1.0)))
    try:
        await asyncio.wait_for(uploading.wait(), timeout=5)
        sent = time.monotonic()
        turn = await speak(client, session.id, "turno-durante-o-upload")
        took = time.monotonic() - sent
    finally:
        laid = await laying_in

    assert turn.status_code == 200, turn.text[:300]
    assert took < 1.0, (
        f"o turno esperou {took:.2f} s pela linha da sessão, presa durante o upload da frase"
    )
    assert laid.status_code == 200, laid.text


@pytest.mark.parametrize("refused", [False, True], ids=["laid-in", "part-changed"])
async def test_the_session_row_is_never_held_while_the_bucket_takes_seconds(
    refused: bool,
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lock = the_session_row_locks_as_postgres_does(monkeypatch)
    the_bucket_takes(monkeypatch, store, 1.0, *THE_BUCKET)
    lock.notes_the_calls(monkeypatch, store, *THE_BUCKET)
    if refused:
        _, _, _, answered = await _refused_while_a_rival_lands(
            client, db_session, store, monkeypatch, Rival.after_the_part_is_read
        )
        assert (answered.status_code, answered.json().get("code")) == (409, "PART_CHANGED")
    else:
        session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
        answered = await re_record(client, session.id, frase.id, spoken(1.0))
        assert answered.status_code == 200, answered.text

    assert lock.calls and lock.spans
    assert lock.made_while_held == [], "o bucket trabalhava com a linha da sessão presa"
    assert max(lock.spans) < 0.5, (
        f"a linha da sessão ficou presa {max(lock.spans):.2f} s enquanto o bucket trabalhava"
    )


async def test_the_spliced_part_is_measured_with_the_session_row_let_go(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, ((frase,),) = await rehearsed_in_wav(db_session, store, [[(0, 2000)]])
    lock = the_session_row_locks_as_postgres_does(monkeypatch)
    measure = sentences.measure_ms_bounded

    async def measuring(audio: bytes) -> int | None:
        await asyncio.sleep(1.0)
        return await measure(audio)

    monkeypatch.setattr(sentences, "measure_ms_bounded", measuring)
    lock.notes_the_calls(monkeypatch, sentences, "measure_ms_bounded")

    laid = await re_record(client, session.id, frase.id, spoken(1.0))

    assert laid.status_code == 200, laid.text
    assert lock.calls and lock.spans
    assert lock.made_while_held == [], "a parte emendada era medida com a linha da sessão presa"
    assert max(lock.spans) < 0.5


async def test_a_part_that_changes_while_its_sentence_is_spliced_refuses_the_sentence_with_part_changed_and_nothing_is_written(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, rival, refused = await _refused_while_a_rival_lands(
        client, db_session, store, monkeypatch, Rival.after_the_part_is_read
    )

    assert (refused.status_code, refused.json().get("code")) == (409, "PART_CHANGED"), refused.text
    await _nothing_of_the_refused_sentence_is_written(rival_factory, session.id, rival)


async def test_a_part_that_changes_while_the_recordings_are_uploaded_refuses_the_sentence_with_part_changed_and_nothing_is_written(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, _, rival, refused = await _refused_while_a_rival_lands(
        client, db_session, store, monkeypatch, Rival.before_a_recording_is_uploaded
    )

    assert (refused.status_code, refused.json().get("code")) == (409, "PART_CHANGED"), refused.text
    await _nothing_of_the_refused_sentence_is_written(rival_factory, session.id, rival)


async def test_the_same_sentence_sent_again_after_part_changed_is_laid_into_the_part_as_it_now_stands(  # noqa: E501
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    rival_factory: async_sessionmaker[AsyncSession],
    store: MemoryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session, first, _, refused = await _refused_while_a_rival_lands(
        client, db_session, store, monkeypatch, Rival.after_the_part_is_read
    )
    assert (refused.status_code, refused.json().get("code")) == (409, "PART_CHANGED"), refused.text

    laid = await re_record(client, session.id, first.id, spoken(0.5), sentence_id="sentence-0002")

    assert laid.status_code == 200, laid.text
    spans = [(one["starts_ms"], one["ends_ms"]) for one in laid.json()["segments"]]
    assert spans == [(0, 900), (900, 2300), (2300, 3300)]
    final = await take_named(db_session, laid.json()["segments"][0]["take_id"])
    assert len(samples_of(store.objects[final.storage_key])) == 52800, (
        "a frase reenviada não entrava na parte como ela ficou depois da outra frase"
    )


def _takes_a_row_lock(call: ast.Call) -> bool:
    if isinstance(call.func, ast.Attribute) and call.func.attr == "with_for_update":
        return True
    return any(
        keyword.arg in {"with_for_update", "for_update"}
        and not (isinstance(keyword.value, ast.Constant) and keyword.value.value is False)
        for keyword in call.keywords
    )


def _on_the_session_row(call: ast.Call) -> bool:
    named = "IRSession" in ast.unparse(call)
    first = call.args[0] if call.args else None
    return named or (isinstance(first, ast.Name) and first.id == "session")


def test_the_session_row_is_taken_for_update_only_by_doors_that_hold_no_bucket() -> None:
    locking = sorted(
        str(path.relative_to(APP.parent))
        for path in APP.rglob("*.py")
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Call) and _takes_a_row_lock(node) and _on_the_session_row(node)
    )

    assert locking == sorted([THE_SENTENCE_DOOR, THE_EXTERNAL_CHECK_OPEN]), (
        "a linha da sessão era travada num lugar novo, que pode segurá-la pelo bucket"
    )
