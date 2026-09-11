"""The per-session coverage channel, read as the tablet reads it: one open request, frames
arriving as they are published, and a comment now and then so the connection is known to
be alive.

`httpx.ASGITransport` awaits the application to completion before it hands a response back,
and this stream ends only when the client hangs up, so the app is driven here by hand: a
`receive` that says `http.disconnect` when the test is done, and a `send` that queues body
chunks as they come.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.internalization_room import CoverageFrame, CoverageView
from app.services.internalization_room.coverage_channel import _subscribers, publish
from app.services.internalization_room.sessions import create_session

IR = "/api/internalization-room"
ROOM_KEY = "sala-de-teste"


@dataclass
class _Listening:
    """One tablet holding the channel open."""

    status: int
    headers: dict[str, str]
    chunks: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)

    async def next_chunk(self) -> bytes:
        return await asyncio.wait_for(self.chunks.get(), timeout=5)


@pytest.fixture()
def channel_app(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    from app.api.internalization_room import router as room_router
    from app.core.config import get_settings
    from app.core.database import get_db
    from app.core.exceptions import register_exception_handlers

    monkeypatch.setattr(get_settings(), "internalization_room_api_key", ROOM_KEY, raising=False)

    test_app = FastAPI()
    test_app.include_router(room_router, prefix=IR)
    register_exception_handlers(test_app)

    async def _get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = _get_db
    return test_app


@pytest.fixture()
async def passage(db_session: AsyncSession) -> str:
    session = await create_session(db_session, pericope="P01", language="pt")
    return session.id


@asynccontextmanager
async def _listening(app: FastAPI, session_id: str) -> AsyncIterator[_Listening]:
    started: asyncio.Future[_Listening] = asyncio.get_running_loop().create_future()
    hung_up = asyncio.Event()
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": f"{IR}/sessions/{session_id}/coverage",
        "raw_path": f"{IR}/sessions/{session_id}/coverage".encode(),
        "query_string": b"",
        "headers": [(b"host", b"test"), (b"x-room-key", ROOM_KEY.encode())],
        "client": ("test", 1),
        "server": ("test", 80),
    }

    async def receive() -> dict[str, Any]:
        await hung_up.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            started.set_result(
                _Listening(
                    status=message["status"],
                    headers={k.decode(): v.decode() for k, v in message["headers"]},
                )
            )
        elif message["type"] == "http.response.body" and message.get("body"):
            (await started).chunks.put_nowait(message["body"])

    serving = asyncio.create_task(app(scope, receive, send))
    try:
        yield await asyncio.wait_for(started, timeout=5)
    finally:
        hung_up.set()
        await serving


async def test_a_published_frame_reaches_the_open_channel_as_one_coverage_event(
    channel_app: FastAPI, passage: str
) -> None:
    async with _listening(channel_app, passage) as tablet:
        assert tablet.status == 200
        assert tablet.headers["content-type"].startswith("text/event-stream")

        publish(
            passage,
            CoverageFrame(
                turn_id="turn-9",
                status="settled",
                coverage=CoverageView(engaged=2, surfaced=3, total=20, absence_index=6),
            ),
        )

        event, data, *rest = (await tablet.next_chunk()).decode().split("\n")

    assert event == "event: coverage"
    assert json.loads(data.removeprefix("data: ")) == {
        "turn_id": "turn-9",
        "status": "settled",
        "coverage": {"engaged": 2, "surfaced": 3, "total": 20, "absence_index": 6},
    }, (
        "a cobertura assentava no servidor e o app só a via adivinhando trinta segundos "
        "e perguntando uma vez"
    )
    assert rest == ["", ""]


async def test_a_quiet_channel_still_says_it_is_alive(
    channel_app: FastAPI, passage: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.api.internalization_room import coverage_channel as channel_api

    monkeypatch.setattr(channel_api, "KEEP_ALIVE_SECONDS", 0.01)

    async with _listening(channel_app, passage) as tablet:
        heard = await tablet.next_chunk()

    assert heard == b": keep-alive\n\n", (
        "um classificador de um minuto deixava a conexão muda, e o proxy a cortava "
        "antes da cobertura chegar"
    )


async def test_a_tablet_that_hangs_up_is_no_longer_a_subscriber(
    channel_app: FastAPI, passage: str
) -> None:
    async with _listening(channel_app, passage):
        assert passage in _subscribers

    assert passage not in _subscribers, (
        "a fila de um tablet que desligou ficava na lista e recebia cada cobertura "
        "até o processo morrer"
    )


async def test_a_session_the_room_does_not_know_is_refused_not_listened_for(
    channel_app: FastAPI,
) -> None:
    async with _listening(channel_app, "sessao-que-nao-existe") as tablet:
        assert tablet.status == 404, (
            "o canal abria um stream sem fim para qualquer id, e a auditoria que percorre "
            "toda rota da sala com um id de mentira ficou pendurada nele"
        )
        assert "sessao-que-nao-existe" not in _subscribers
