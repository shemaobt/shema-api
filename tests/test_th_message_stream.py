import sys
from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.api.translation_helper import chats as chats_router
from app.db.models.translation_helper import (
    ChatMessageRole,
    THChatMessage,
)
from app.services.translation_helper.stream_message import stream_message
from tests.baker import make_th_agent_prompt, make_th_chat, make_user

_STREAM_MOD = sys.modules["app.services.translation_helper.stream_message"]


def _patch_stream(monkeypatch, chunks: list[str]) -> None:
    async def fake_stream(*, system_prompt, contents, settings) -> AsyncIterator[str]:
        for c in chunks:
            yield c

    monkeypatch.setattr(_STREAM_MOD, "_stream_chunks", fake_stream)


def _patch_stream_then_raise(monkeypatch, chunks_before_error: list[str], exc: Exception) -> None:
    async def fake_stream(*, system_prompt, contents, settings) -> AsyncIterator[str]:
        for c in chunks_before_error:
            yield c
        raise exc

    monkeypatch.setattr(_STREAM_MOD, "_stream_chunks", fake_stream)


async def test_stream_message_yields_chunks_in_order(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_stream_a@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    _patch_stream(monkeypatch, ["Hello", " ", "world"])

    out: list[str] = []
    async for piece in stream_message(db_session, chat.id, user.id, "hi"):
        out.append(piece)
    assert out == ["Hello", " ", "world"]


async def test_stream_message_persists_concatenated_text(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_stream_b@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    _patch_stream(monkeypatch, ["A", "B", "C"])

    async for _ in stream_message(db_session, chat.id, user.id, "hi"):
        pass

    rows = (
        (
            await db_session.execute(
                select(THChatMessage)
                .where(THChatMessage.chat_id == chat.id)
                .order_by(THChatMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert [r.role for r in rows] == [ChatMessageRole.USER, ChatMessageRole.ASSISTANT]
    assert rows[0].content == "hi"
    assert rows[1].content == "ABC"


async def test_stream_message_persists_user_turn_and_partial_on_mid_stream_error(
    monkeypatch, db_session
) -> None:
    """If Gemini raises mid-stream, the user's question and the partial assistant
    text both survive so the chat history stays coherent on reload."""
    user = await make_user(db_session, email="th_stream_c@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    _patch_stream_then_raise(
        monkeypatch, ["partial ", "response"], RuntimeError("LLM blew up mid-stream")
    )

    received: list[str] = []
    with pytest.raises(RuntimeError, match="LLM blew up"):
        async for piece in stream_message(db_session, chat.id, user.id, "my question"):
            received.append(piece)

    assert received == ["partial ", "response"]

    rows = (
        (
            await db_session.execute(
                select(THChatMessage)
                .where(THChatMessage.chat_id == chat.id)
                .order_by(THChatMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert [r.role for r in rows] == [ChatMessageRole.USER, ChatMessageRole.ASSISTANT]
    assert rows[0].content == "my question"
    assert rows[1].content == "partial response"


async def test_stream_message_persists_user_turn_when_stream_fails_before_any_chunk(
    monkeypatch, db_session
) -> None:
    """No assistant chunks collected: only the user turn is saved, never an empty
    assistant row."""
    user = await make_user(db_session, email="th_stream_d@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    _patch_stream_then_raise(monkeypatch, [], RuntimeError("LLM unreachable"))

    received: list[str] = []
    with pytest.raises(RuntimeError):
        async for piece in stream_message(db_session, chat.id, user.id, "question"):
            received.append(piece)

    assert received == []

    rows = (
        (
            await db_session.execute(
                select(THChatMessage)
                .where(THChatMessage.chat_id == chat.id)
                .order_by(THChatMessage.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    assert [r.role for r in rows] == [ChatMessageRole.USER]
    assert rows[0].content == "question"


async def test_stream_chat_message_error_event_does_not_leak_exception(monkeypatch) -> None:
    """Pins B-5: SSE error events must show a generic message, not the raw exception."""
    secret = "SUPER_SECRET_INTERNAL_DETAIL_xyz123"

    async def boom(*args, **kwargs):
        raise RuntimeError(secret)
        yield  # pragma: no cover — make this an async generator

    fake_service = SimpleNamespace(stream_message=boom)
    monkeypatch.setattr(chats_router, "th_service", fake_service)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chats_router, "AsyncSessionLocal", lambda: _FakeSession())

    fake_user = SimpleNamespace(id="user-1")
    payload = SimpleNamespace(content="hi", agent_id=None)

    response = await chats_router.stream_chat_message(
        chat_id="chat-1",
        payload=payload,
        user=fake_user,
    )

    body = b"".join([chunk async for chunk in response.body_iterator])
    decoded = body.decode("utf-8")
    assert "Streaming failed" in decoded
    assert secret not in decoded
    assert "RuntimeError" not in decoded


async def test_stream_chat_message_sets_anti_buffering_headers(monkeypatch) -> None:
    """Without these headers, nginx and other intermediaries buffer SSE responses,
    which collapses the streaming UX into a single delayed burst."""

    async def empty(*args, **kwargs):
        yield "chunk"

    fake_service = SimpleNamespace(stream_message=empty)
    monkeypatch.setattr(chats_router, "th_service", fake_service)

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(chats_router, "AsyncSessionLocal", lambda: _FakeSession())

    fake_user = SimpleNamespace(id="user-1")
    payload = SimpleNamespace(content="hi", agent_id=None)

    response = await chats_router.stream_chat_message(
        chat_id="chat-1",
        payload=payload,
        user=fake_user,
    )

    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("cache-control") == "no-cache"
    assert response.media_type == "text/event-stream"
