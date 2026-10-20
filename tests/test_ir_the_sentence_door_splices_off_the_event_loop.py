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
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.internalization_room import sentences
from tests.hard_stretch_harness import MemoryStore
from tests.room_harness import room_client, the_bucket_is_in_memory
from tests.sentence_harness import re_record, rehearsed_in_wav, spoken


@pytest.fixture()
def store(monkeypatch: pytest.MonkeyPatch) -> MemoryStore:
    return the_bucket_is_in_memory(monkeypatch)


@pytest.fixture()
async def client(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch, store: MemoryStore):
    async with room_client(db_session, monkeypatch) as door:
        yield door


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
