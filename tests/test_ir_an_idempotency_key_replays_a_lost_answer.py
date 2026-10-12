from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
from fastapi import HTTPException
from httpx import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.internalization_room._deps import DEVICE_CREDENTIAL_HEADER
from app.core.exceptions import ConflictError
from app.services.internalization_room import idempotency
from tests.device_harness import TABLET_TEAM, a_linked_tablet
from tests.hard_stretch_harness import (
    AUDIO,
    DEVICE,
    IR,
    SLICES,
)
from tests.hard_stretch_harness import (
    MemoryStore as _MemoryStore,
)
from tests.hard_stretch_harness import (
    a_session as _a_session,
)
from tests.hard_stretch_harness import (
    current as _current,
)
from tests.hard_stretch_harness import (
    marks as _marks,
)
from tests.hard_stretch_harness import (
    rehearse as _rehearse,
)
from tests.release_harness import a_claimed_device

OTHER_AUDIO = b"a equipe contou este trecho de outro jeito"
CLOCK = "app.services.internalization_room.idempotency.utcnow"
WAIT_S = 10


class Held:
    def __init__(self, text: str) -> None:
        self.text = text
        self.reached = asyncio.Event()
        self.released = asyncio.Event()

    async def answered(self) -> str:
        self.reached.set()
        await self.released.wait()
        return self.text

    async def until_reached(self) -> None:
        await asyncio.wait_for(self.reached.wait(), timeout=WAIT_S)


class Transcriber:
    def __init__(self) -> None:
        self.answers: list[Any] = []

    async def __call__(self, *_: Any, **__: Any) -> str:
        answer = self.answers.pop(0) if self.answers else "algo que a equipe contou"
        if isinstance(answer, Held):
            return await answer.answered()
        if isinstance(answer, BaseException):
            raise answer
        return str(answer)


@pytest.fixture()
async def client(db_session: AsyncSession, test_engine, monkeypatch: pytest.MonkeyPatch):
    from fastapi import FastAPI

    from app.api.internalization_room import back_translation as bt_api
    from app.api.internalization_room import router as room_router
    from app.api.internalization_room import segments as segments_api
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers
    from app.services.internalization_room import takes as takes_service

    transcriber = Transcriber()
    monkeypatch.setattr(bt_api, "heard", transcriber)
    monkeypatch.setattr(segments_api, "heard", transcriber)
    bucket = _MemoryStore()
    monkeypatch.setattr(takes_service, "_store", lambda *_, **__: bucket)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    one_session_per_request = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession
    )

    async def _get_db():
        async with one_session_per_request() as db:
            yield db

    test_app.dependency_overrides[get_db] = _get_db
    transport = ASGITransport(app=test_app, raise_app_exceptions=False)
    tablet = await a_linked_tablet(db_session, team_id=TABLET_TEAM)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
        headers={DEVICE_CREDENTIAL_HEADER: tablet.credential},
    ) as c:
        c.transcriber = transcriber  # type: ignore[attr-defined]
        yield c


def _answers(client: httpx.AsyncClient) -> list[Any]:
    return client.transcriber.answers  # type: ignore[attr-defined]


def _headers(
    key: str | None,
    *,
    device: str | None = DEVICE,
    credential: str | None = None,
) -> dict[str, str]:
    headers = {}
    if device is not None:
        headers["X-Room-Device"] = device
    if credential is not None:
        headers[DEVICE_CREDENTIAL_HEADER] = credential
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


async def _chunk(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    stretch: int,
    *,
    key: str | None = None,
    again: bool = False,
    audio: bytes = AUDIO,
    device: str | None = DEVICE,
    credential: str | None = None,
) -> httpx.Response:
    starts, ends = SLICES[stretch - 1]
    data = {"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)}
    if again:
        data["retelling"] = "true"
    return await client.post(
        f"{IR}/sessions/{session_id}/back-translation/chunks",
        headers=_headers(key, device=device, credential=credential),
        data=data,
        files={"file": ("trecho.m4a", audio, "audio/mp4")},
    )


async def _replace(
    client: httpx.AsyncClient,
    session_id: str,
    take_id: str,
    segment_id: str,
    stretch: int,
    *,
    key: str | None = None,
) -> httpx.Response:
    starts, ends = SLICES[stretch - 1]
    return await client.post(
        f"{IR}/sessions/{session_id}/segments/{segment_id}/replace",
        headers=_headers(key),
        data={"take_id": take_id, "starts_ms": str(starts), "ends_ms": str(ends)},
        files={"file": ("correcao.m4a", AUDIO, "audio/mp4")},
    )


async def _a_rehearsed_session(db: AsyncSession, client: httpx.AsyncClient) -> tuple[str, str]:
    session_id = await _a_session(db)
    return session_id, await _rehearse(client, session_id)


async def _told(client: httpx.AsyncClient, session_id: str, take_id: str) -> str:
    _answers(client).append("o trecho 1")
    told = await _chunk(client, session_id, take_id, 1)
    assert told.status_code == 200, told.text
    return session_id


async def test_one_stretch_per_key(client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)

    first = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    again = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert first.status_code == 200, first.text
    assert again.status_code == first.status_code
    assert again.json() == first.json()
    assert len(await _current(db_session, session_id)) == 1


@pytest.mark.parametrize(
    ("heard", "status", "tellings"),
    [("o trecho 1 corrigido", 200, 2), ("", 422, 1)],
    ids=["heard", "empty"],
)
async def test_one_correction_per_key(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    heard: str,
    status: int,
    tellings: int,
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    await _told(client, session_id, take_id)
    [stretch] = await _current(db_session, session_id)

    _answers(client).append(heard)
    first = await _replace(client, session_id, take_id, stretch.id, 1, key="uma-correcao")
    again = await _replace(client, session_id, take_id, stretch.id, 1, key="uma-correcao")

    assert first.status_code == status, first.text
    assert again.status_code == first.status_code
    assert again.json() == first.json()
    [standing] = await _current(db_session, session_id)
    assert standing.tellings == tellings


async def test_a_key_reused_with_another_body_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    first = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    assert first.status_code == 200, first.text

    reused = await _chunk(client, session_id, take_id, 1, key="um-trecho", audio=OTHER_AUDIO)

    assert reused.status_code == 422, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert len(await _current(db_session, session_id)) == 1


async def test_a_key_reused_on_another_session_is_refused_not_replayed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    other_id, other_take_id = await _a_rehearsed_session(db_session, client)
    first = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    assert first.status_code == 200, first.text

    reused = await _chunk(client, other_id, other_take_id, 1, key="um-trecho")

    assert reused.status_code == 422, reused.text
    assert reused.json()["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert await _current(db_session, other_id) == []


async def test_a_key_in_flight_answers_409(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    held = Held("o trecho 1")
    _answers(client).append(held)

    first = asyncio.create_task(_chunk(client, session_id, take_id, 1, key="um-trecho"))
    try:
        await held.until_reached()
        in_flight = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    finally:
        held.released.set()
    answered = await first

    assert in_flight.status_code == 409, in_flight.text
    assert in_flight.json()["code"] == "IDEMPOTENCY_KEY_IN_FLIGHT"
    assert answered.status_code == 200, answered.text
    assert len(await _current(db_session, session_id)) == 1


async def test_a_key_older_than_a_day_is_a_new_request(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    now = [datetime(2026, 9, 30, 9, 0, tzinfo=UTC)]
    monkeypatch.setattr(CLOCK, lambda: now[0])
    first = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    assert first.status_code == 200, first.text

    now[0] += timedelta(hours=24, minutes=1)
    later = await _chunk(client, session_id, take_id, 1, key="um-trecho", audio=OTHER_AUDIO)

    assert later.status_code == 200, later.text


@pytest.mark.parametrize(
    ("unsettled", "status"),
    [
        pytest.param(lambda: HTTPException(status_code=429, detail="slow down"), 429, id="429"),
        pytest.param(lambda: ConflictError("written by another turn"), 409, id="409"),
    ],
)
async def test_an_unsettled_answer_leaves_no_row(
    client: httpx.AsyncClient, db_session: AsyncSession, unsettled: Any, status: int
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    _answers(client).extend([unsettled(), "o trecho 1"])

    failed = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    resent = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    replayed = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert failed.status_code == status, failed.text
    assert resent.status_code == 200, resent.text
    assert replayed.status_code == 200, replayed.text
    assert replayed.json() == resent.json()
    assert len(await _current(db_session, session_id)) == 1


async def test_a_settled_refusal_is_replayed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    _answers(client).extend(["", "o trecho 1"])

    refused = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    replayed = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert refused.status_code == 422, refused.text
    assert refused.json()["code"] == "WORDLESS_TELLING"
    assert replayed.status_code == refused.status_code
    assert replayed.json() == refused.json()
    assert await _current(db_session, session_id) == []


async def test_a_refused_credential_does_not_spend_the_key(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)

    refused = await _chunk(client, session_id, take_id, 1, key="um-trecho", credential="errada")
    resent = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert refused.status_code == 401, refused.text
    assert resent.status_code == 200, resent.text
    assert len(await _current(db_session, session_id)) == 1


async def test_a_replay_is_answered_only_to_a_caller_the_door_lets_in(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    first = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    assert first.status_code == 200, first.text

    stranger = await _chunk(client, session_id, take_id, 1, key="um-trecho", credential="errada")

    assert stranger.status_code == 401, stranger.text


async def test_an_empty_key_is_no_key(client: httpx.AsyncClient, db_session: AsyncSession) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)

    first = await _chunk(client, session_id, take_id, 1, key="")
    other = await _chunk(client, session_id, take_id, 2, key="", audio=OTHER_AUDIO)

    assert first.status_code == 200, first.text
    assert other.status_code == 200, other.text
    assert len(await _current(db_session, session_id)) == 2


async def test_a_retold_chunk_sent_twice_under_one_key_counts_one_telling(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    await _told(client, session_id, take_id)
    _answers(client).append("o trecho 1 de novo")
    retold = await _chunk(client, session_id, take_id, 1, again=True)
    assert retold.status_code == 200, retold.text

    _answers(client).append("o trecho 1 pela terceira vez")
    first = await _chunk(client, session_id, take_id, 1, key="terceira", again=True)
    again = await _chunk(client, session_id, take_id, 1, key="terceira", again=True)

    assert first.status_code == 200, first.text
    assert again.json() == first.json()
    [standing] = await _current(db_session, session_id)
    assert standing.tellings == 3
    assert len(await _marks(db_session, session_id)) == 1


async def test_a_stretch_superseded_while_a_chunk_is_heard_refuses_the_chunk(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    await _told(client, session_id, take_id)
    [stretch] = await _current(db_session, session_id)
    held = Held("o trecho 1 de novo")
    _answers(client).extend([held, "o trecho 1 corrigido"])

    chunk = asyncio.create_task(_chunk(client, session_id, take_id, 1, again=True))
    try:
        await held.until_reached()
        superseded = await _replace(client, session_id, take_id, stretch.id, 1)
    finally:
        held.released.set()
    refused = await chunk

    assert superseded.status_code == 200, superseded.text
    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "STRETCH_NO_LONGER_COUNTS"
    assert len(await _current(db_session, session_id)) == 1


async def test_a_stretch_superseded_while_a_correction_is_heard_refuses_the_correction(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    await _told(client, session_id, take_id)
    [stretch] = await _current(db_session, session_id)
    held = Held("a primeira correcao")
    _answers(client).extend([held, "a segunda correcao"])

    correction = asyncio.create_task(_replace(client, session_id, take_id, stretch.id, 1))
    try:
        await held.until_reached()
        superseded = await _replace(client, session_id, take_id, stretch.id, 1)
    finally:
        held.released.set()
    refused = await correction

    assert superseded.status_code == 200, superseded.text
    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "STRETCH_NO_LONGER_COUNTS"
    assert len(await _current(db_session, session_id)) == 1


async def test_a_claim_left_unanswered_past_the_request_timeout_is_taken_over(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    now = [datetime(2026, 9, 30, 9, 0, tzinfo=UTC)]
    monkeypatch.setattr(CLOCK, lambda: now[0])
    abandoned = Held("")
    _answers(client).extend([abandoned, "o trecho 1"])
    late = asyncio.create_task(_chunk(client, session_id, take_id, 1, key="um-trecho"))
    try:
        await abandoned.until_reached()
        now[0] += timedelta(seconds=301)
        taken_over = await _chunk(client, session_id, take_id, 1, key="um-trecho")
    finally:
        abandoned.released.set()
    await late
    replayed = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert taken_over.status_code == 200, taken_over.text
    assert replayed.status_code == 200, replayed.text
    assert replayed.json() == taken_over.json()


async def test_a_request_missing_its_device_does_not_spend_the_key(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)

    refused = await _chunk(client, session_id, take_id, 1, key="um-trecho", device=None)
    resent = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert refused.status_code == 400, refused.text
    assert resent.status_code == 200, resent.text
    assert len(await _current(db_session, session_id)) == 1


async def test_another_projects_device_is_refused_as_without_a_key_never_replayed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    own = (await a_linked_tablet(db_session, team_id=TABLET_TEAM)).credential
    _, stranger = await a_claimed_device(db_session, email="bia@example.com")
    session_id = await _a_session(db_session, team_id=TABLET_TEAM)
    take_id = await _rehearse(client, session_id)
    first = await _chunk(client, session_id, take_id, 1, key="um-trecho", credential=own)
    assert first.status_code == 200, first.text

    keyless = await _chunk(client, session_id, take_id, 1, credential=stranger)
    keyed = await _chunk(client, session_id, take_id, 1, key="um-trecho", credential=stranger)

    assert keyless.status_code == 404, keyless.text
    assert keyed.status_code == keyless.status_code, keyed.text
    assert keyed.json()["code"] == keyless.json()["code"]


async def test_a_key_longer_than_255_characters_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)

    refused = await _chunk(client, session_id, take_id, 1, key="k" * 256)

    assert refused.status_code == 400, refused.text
    assert refused.json()["code"] == "BAD_REQUEST"
    assert await _current(db_session, session_id) == []


async def test_a_request_cancelled_while_its_answer_is_stored_keeps_the_answer(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    store = idempotency.settle
    storing = asyncio.Event()
    let_go = asyncio.Event()
    stored = asyncio.Event()

    async def held_while_storing(*args: Any, **kwargs: Any) -> None:
        storing.set()
        await let_go.wait()
        await store(*args, **kwargs)
        stored.set()

    monkeypatch.setattr(idempotency, "settle", held_while_storing)
    cancelled = asyncio.create_task(_chunk(client, session_id, take_id, 1, key="um-trecho"))
    await asyncio.wait_for(storing.wait(), timeout=WAIT_S)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    let_go.set()
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(stored.wait(), timeout=2)

    resent = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert resent.status_code == 200, resent.text
    assert len(await _current(db_session, session_id)) == 1


async def test_a_store_that_fails_after_a_cancellation_frees_the_key(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    session_id, take_id = await _a_rehearsed_session(db_session, client)
    let_go = asyncio.Event()
    storing = asyncio.Event()
    freed = asyncio.Event()
    store = idempotency.settle
    free = idempotency.release

    async def fails_while_storing(*_: Any, **__: Any) -> None:
        storing.set()
        await let_go.wait()
        raise ConnectionError("the database went away")

    async def freeing(*args: Any, **kwargs: Any) -> None:
        await free(*args, **kwargs)
        freed.set()

    monkeypatch.setattr(idempotency, "settle", fails_while_storing)
    monkeypatch.setattr(idempotency, "release", freeing)
    cancelled = asyncio.create_task(_chunk(client, session_id, take_id, 1, key="um-trecho"))
    await asyncio.wait_for(storing.wait(), timeout=WAIT_S)
    cancelled.cancel()
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    let_go.set()
    with contextlib.suppress(TimeoutError):
        await asyncio.wait_for(freed.wait(), timeout=2)
    monkeypatch.setattr(idempotency, "settle", store)

    resent = await _chunk(client, session_id, take_id, 1, key="um-trecho")

    assert resent.status_code == 200, resent.text
    assert len(await _current(db_session, session_id)) == 2
