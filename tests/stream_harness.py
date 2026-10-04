from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

App = Callable[..., Awaitable[None]]


@dataclass
class Listening:
    status: int
    headers: dict[str, str]
    chunks: asyncio.Queue[bytes] = field(default_factory=asyncio.Queue)

    async def next_chunk(self) -> bytes:
        return await asyncio.wait_for(self.chunks.get(), timeout=5)


@asynccontextmanager
async def listening(app: App, path: str, headers: dict[str, str]) -> AsyncIterator[Listening]:
    started: asyncio.Future[Listening] = asyncio.get_running_loop().create_future()
    hung_up = asyncio.Event()
    scope = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "headers": [(b"host", b"test")]
        + [(name.lower().encode(), value.encode()) for name, value in headers.items()],
        "client": ("test", 1),
        "server": ("test", 80),
    }

    async def receive() -> dict[str, Any]:
        await hung_up.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            started.set_result(
                Listening(
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


async def opening_status(app: App, path: str, headers: dict[str, str]) -> int:
    async with listening(app, path, headers) as opened:
        return opened.status
