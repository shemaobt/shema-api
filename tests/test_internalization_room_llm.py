import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.services.internalization_room import llm


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "anthropic_api_key": "sk-ant-fake",
    }
    base.update(overrides)
    return Settings(**base)


class FakeMessages:
    def __init__(self, reply: SimpleNamespace):
        self.reply = reply
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.kwargs = kwargs
        return self.reply


class FakeClient:
    def __init__(self, reply: SimpleNamespace, **options: Any):
        self.messages = FakeMessages(reply)
        self.options = options


def _reply(
    text: str,
    stop_reason: str = "end_turn",
    output: int = 0,
    cache_read: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model="claude-fable-5-1",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=output,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=0,
        ),
    )


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch):
    def _install(reply: SimpleNamespace) -> dict[str, FakeClient]:
        holder: dict[str, FakeClient] = {}

        def _build(**options: Any) -> FakeClient:
            holder["client"] = FakeClient(reply, **options)
            return holder["client"]

        monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
        return holder

    return _install


async def test_the_guide_drafts_on_the_frontier_model_the_doctrine_names(fake_client):
    holder = fake_client(_reply("ok"))

    await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert holder["client"].messages.kwargs["model"] == "claude-fable-5-1", (
        "a sala rascunhava no gemini-3-flash-preview, o modelo da falha do dia 3 de setembro"
    )


async def test_a_truncated_answer_is_reported_not_swallowed(fake_client, caplog):
    fake_client(_reply('{"verd', stop_reason="max_tokens", output=45))

    with caplog.at_level(logging.WARNING):
        await llm.call_agent(
            system_prompt="s",
            user_content="u",
            max_output_tokens=1200,
            settings=_settings(),
        )

    assert "max_tokens" in caplog.text
    assert "1200" in caplog.text


async def test_a_finished_answer_stays_quiet(fake_client, caplog):
    fake_client(_reply("ok", output=2))

    with caplog.at_level(logging.WARNING):
        text = await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert text == "ok"
    assert caplog.text == ""


async def test_an_empty_answer_still_says_why(fake_client, caplog):
    reply = _reply("ok")
    reply.content = []

    fake_client(reply)
    with caplog.at_level(logging.WARNING):
        assert await llm.call_agent(system_prompt="s", user_content="u", settings=_settings()) == ""

    assert "no content" in caplog.text
