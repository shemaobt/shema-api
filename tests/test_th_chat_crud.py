import pytest
from sqlalchemy import select

from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.translation_helper import (
    AgentId,
    ChatMessageRole,
    THChat,
    THChatMessage,
)
from app.services.translation_helper.create_chat import create_chat
from app.services.translation_helper.delete_chat import delete_chat
from app.services.translation_helper.get_chat_or_404 import get_chat_or_404
from app.services.translation_helper.list_chats_for_user import list_chats_for_user
from app.services.translation_helper.list_messages import list_messages
from app.services.translation_helper.update_chat import update_chat
from tests.baker import make_th_chat, make_th_message, make_user


async def test_create_chat_default(db_session) -> None:
    user = await make_user(db_session, email="th_a@test.com")
    chat = await create_chat(db_session, user.id)
    assert chat.id
    assert chat.user_id == user.id
    assert chat.agent_id == AgentId.STORYTELLER
    assert chat.title is None


async def test_create_chat_custom_agent_and_title(db_session) -> None:
    user = await make_user(db_session, email="th_b@test.com")
    chat = await create_chat(db_session, user.id, agent_id=AgentId.BACKTRANS, title="Romans 8")
    assert chat.agent_id == AgentId.BACKTRANS
    assert chat.title == "Romans 8"


async def test_list_chats_for_user_filters_by_owner(db_session) -> None:
    alice = await make_user(db_session, email="th_alice@test.com")
    bob = await make_user(db_session, email="th_bob@test.com")
    await make_th_chat(db_session, alice.id, title="alice 1")
    await make_th_chat(db_session, alice.id, title="alice 2")
    await make_th_chat(db_session, bob.id, title="bob 1")

    alice_rows = await list_chats_for_user(db_session, alice.id)
    bob_rows = await list_chats_for_user(db_session, bob.id)
    assert len(alice_rows) == 2
    assert len(bob_rows) == 1
    assert {r["title"] for r in alice_rows} == {"alice 1", "alice 2"}


async def test_get_chat_or_404_success(db_session) -> None:
    user = await make_user(db_session, email="th_c@test.com")
    chat = await make_th_chat(db_session, user.id)
    found = await get_chat_or_404(db_session, chat.id, user_id=user.id)
    assert found.id == chat.id


async def test_get_chat_or_404_raises_when_missing(db_session) -> None:
    with pytest.raises(NotFoundError, match=r"Chat .* not found"):
        await get_chat_or_404(db_session, "nonexistent")


async def test_get_chat_or_404_raises_when_other_user(db_session) -> None:
    owner = await make_user(db_session, email="th_owner@test.com")
    intruder = await make_user(db_session, email="th_intruder@test.com")
    chat = await make_th_chat(db_session, owner.id)
    with pytest.raises(AuthorizationError):
        await get_chat_or_404(db_session, chat.id, user_id=intruder.id)


async def test_update_chat_title_and_agent(db_session) -> None:
    user = await make_user(db_session, email="th_d@test.com")
    chat = await make_th_chat(db_session, user.id, title="old")
    updated = await update_chat(db_session, chat.id, user.id, title="new", agent_id=AgentId.ORAL)
    assert updated.title == "new"
    assert updated.agent_id == AgentId.ORAL


async def test_delete_chat_cascades_messages(db_session) -> None:
    user = await make_user(db_session, email="th_e@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_message(db_session, chat.id, content="m1")
    await make_th_message(db_session, chat.id, role=ChatMessageRole.ASSISTANT, content="m2")

    await delete_chat(db_session, chat.id, user.id)

    remaining_chats = (
        await db_session.execute(select(THChat).where(THChat.id == chat.id))
    ).scalar_one_or_none()
    assert remaining_chats is None
    remaining_msgs = (
        await db_session.execute(select(THChatMessage).where(THChatMessage.chat_id == chat.id))
    ).all()
    assert remaining_msgs == []


async def test_list_messages_ordered_asc(db_session) -> None:
    user = await make_user(db_session, email="th_f@test.com")
    chat = await make_th_chat(db_session, user.id)
    m1 = await make_th_message(db_session, chat.id, content="first")
    m2 = await make_th_message(
        db_session, chat.id, role=ChatMessageRole.ASSISTANT, content="second"
    )
    msgs = await list_messages(db_session, chat.id)
    assert [m.id for m in msgs] == [m1.id, m2.id]
    assert [m.content for m in msgs] == ["first", "second"]


async def test_list_messages_with_limit_returns_most_recent_in_chronological_order(
    db_session,
) -> None:
    """Limit means 'tail N' — the newest messages, still oldest-to-newest in the
    returned list — so the UI can render the most recent context without
    silently dropping the latest turns."""
    user = await make_user(db_session, email="th_g@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_message(db_session, chat.id, content="m1")
    await make_th_message(db_session, chat.id, role=ChatMessageRole.ASSISTANT, content="m2")
    await make_th_message(db_session, chat.id, content="m3")
    await make_th_message(db_session, chat.id, role=ChatMessageRole.ASSISTANT, content="m4")
    await make_th_message(db_session, chat.id, content="m5")

    last_two = await list_messages(db_session, chat.id, limit=2)
    assert [m.content for m in last_two] == ["m4", "m5"]

    last_three = await list_messages(db_session, chat.id, limit=3)
    assert [m.content for m in last_three] == ["m3", "m4", "m5"]


async def test_list_messages_limit_larger_than_count_returns_all(db_session) -> None:
    user = await make_user(db_session, email="th_h@test.com")
    chat = await make_th_chat(db_session, user.id)
    await make_th_message(db_session, chat.id, content="only")

    msgs = await list_messages(db_session, chat.id, limit=50)
    assert [m.content for m in msgs] == ["only"]
