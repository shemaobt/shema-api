import sys

import pytest
from sqlalchemy import select

from app.core.exceptions import NotFoundError
from app.db.models.translation_helper import (
    AgentId,
    ChatMessageRole,
    THChatMessage,
)
from app.services.translation_helper.send_message import send_message
from tests.baker import make_th_agent_prompt, make_th_chat, make_th_message, make_user

_SEND_MOD = sys.modules["app.services.translation_helper.send_message"]


def _patch_genai(monkeypatch, *, assistant_text: str, title_text: str = "auto title") -> dict:
    """Monkeypatch send_message._generate_assistant_text and _generate_title."""
    calls: dict[str, list] = {"assistant": [], "title": []}

    async def fake_assistant_text(*, system_prompt, contents, settings):
        calls["assistant"].append({"system_prompt": system_prompt, "contents": contents})
        return assistant_text

    async def fake_title(user_message, settings):
        calls["title"].append(user_message)
        return title_text

    monkeypatch.setattr(_SEND_MOD, "_generate_assistant_text", fake_assistant_text)
    monkeypatch.setattr(_SEND_MOD, "_generate_title", fake_title)
    return calls


async def test_send_message_persists_both_turns(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_msg_a@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="STORY PROMPT")

    calls = _patch_genai(monkeypatch, assistant_text="ASSISTANT REPLY")

    assistant_msg = await send_message(db_session, chat.id, user.id, "Tell me about Ruth")

    assert assistant_msg.role == ChatMessageRole.ASSISTANT
    assert assistant_msg.content == "ASSISTANT REPLY"
    assert assistant_msg.agent_id == AgentId.STORYTELLER

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
    assert rows[0].content == "Tell me about Ruth"
    assert rows[1].content == "ASSISTANT REPLY"

    assert calls["assistant"][0]["system_prompt"] == "STORY PROMPT"


async def test_send_message_auto_titles_first_user_message(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_msg_b@test.com")
    chat = await make_th_chat(db_session, user.id, title=None)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    _patch_genai(monkeypatch, assistant_text="reply", title_text="The Story of Ruth")
    await send_message(db_session, chat.id, user.id, "Tell me about Ruth")

    await db_session.refresh(chat)
    assert chat.title == "The Story of Ruth"


async def test_send_message_no_title_overwrite_on_subsequent(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_msg_c@test.com")
    chat = await make_th_chat(db_session, user.id, title="My existing title")
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")
    await make_th_message(db_session, chat.id, content="prior user msg")

    _patch_genai(monkeypatch, assistant_text="r", title_text="WOULD CLOBBER")
    await send_message(db_session, chat.id, user.id, "next turn")

    await db_session.refresh(chat)
    assert chat.title == "My existing title"


async def test_send_message_raises_for_unknown_chat(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_msg_d@test.com")
    _patch_genai(monkeypatch, assistant_text="never called")
    with pytest.raises(NotFoundError, match=r"Chat .* not found"):
        await send_message(db_session, "missing-chat-id", user.id, "hi")


async def test_send_message_falls_back_to_content_when_title_generation_fails(
    monkeypatch, db_session
) -> None:
    """B-3: if _generate_title raises, chat.title should fall back to a truncated
    version of the user's first message, not stay None forever."""
    user = await make_user(db_session, email="th_title_fallback@test.com")
    chat = await make_th_chat(db_session, user.id, title=None)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    async def title_boom(user_message, settings):
        raise RuntimeError("title quota exceeded")

    async def fake_assistant_text(*, system_prompt, contents, settings):
        return "reply"

    monkeypatch.setattr(_SEND_MOD, "_generate_assistant_text", fake_assistant_text)
    monkeypatch.setattr(_SEND_MOD, "_generate_title", title_boom)

    user_msg = "Tell me about the Prodigal Son in three sentences"
    await send_message(db_session, chat.id, user.id, user_msg)

    await db_session.refresh(chat)
    assert chat.title is not None
    assert chat.title != "New chat"  # don't fall back to the agent literal
    assert chat.title.startswith("Tell me about")


async def test_send_message_does_not_persist_user_msg_when_gemini_fails(
    monkeypatch, db_session
) -> None:
    """Pins B-1: the user message must not be flushed independently of the commit.

    With the flush dropped, `db.add(user_msg)` only stages the row in the session.
    When Gemini raises, the row is still in `session.new` and would be discarded
    by `get_db`'s `async with` rollback in production. Here we assert directly
    on the session's pending state.
    """
    user = await make_user(db_session, email="th_msg_rollback@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_agent_prompt(db_session, agent_id="storyteller", prompt="P")

    async def boom(*, system_prompt, contents, settings):
        raise RuntimeError("gemini exploded")

    monkeypatch.setattr(_SEND_MOD, "_generate_assistant_text", boom)

    pending_before = {
        (m.chat_id, m.role, m.content) for m in db_session.new if isinstance(m, THChatMessage)
    }
    assert pending_before == set()

    with pytest.raises(RuntimeError, match="gemini exploded"):
        await send_message(db_session, chat.id, user.id, "this should not persist")

    pending_msgs = [m for m in db_session.new if isinstance(m, THChatMessage)]
    assert len(pending_msgs) == 1
    assert pending_msgs[0].role == ChatMessageRole.USER
    assert pending_msgs[0].content == "this should not persist"


async def test_send_message_uses_agent_override(monkeypatch, db_session) -> None:
    user = await make_user(db_session, email="th_msg_e@test.com")
    chat = await make_th_chat(db_session, user.id, agent_id=AgentId.STORYTELLER)
    await make_th_agent_prompt(db_session, agent_id="oral", prompt="ORAL PROMPT")

    calls = _patch_genai(monkeypatch, assistant_text="oral reply")
    msg = await send_message(db_session, chat.id, user.id, "speak it", agent_id=AgentId.ORAL)

    assert msg.agent_id == AgentId.ORAL
    assert calls["assistant"][0]["system_prompt"] == "ORAL PROMPT"
