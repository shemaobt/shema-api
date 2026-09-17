import logging
from typing import Any

import pytest
from google.genai import types

from app.core.config import Settings
from app.services.internalization_room import llm


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake")


class FakeModels:
    def __init__(self, response: types.GenerateContentResponse):
        self.response = response
        self.config: types.GenerateContentConfig | None = None

    async def generate_content(self, **kwargs: Any) -> types.GenerateContentResponse:
        self.config = kwargs["config"]
        return self.response


class FakeClient:
    def __init__(self, response: types.GenerateContentResponse):
        self.aio = type("Aio", (), {"models": FakeModels(response)})()


def _response(
    text: str, reason: types.FinishReason, thoughts: int = 0, output: int = 0
) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(
                content=types.Content(role="model", parts=[types.Part(text=text)]),
                finish_reason=reason,
            )
        ],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            thoughts_token_count=thoughts, candidates_token_count=output
        ),
    )


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch):
    def _install(response: types.GenerateContentResponse) -> FakeClient:
        client = FakeClient(response)
        monkeypatch.setattr(llm.genai, "Client", lambda **_: client)
        return client

    return _install


@pytest.mark.asyncio
async def test_every_room_call_names_a_thinking_level(fake_client):
    client = fake_client(_response("ok", types.FinishReason.STOP))

    await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    thinking = client.aio.models.config.thinking_config
    assert thinking is not None, (
        "sem nível explícito o modelo pensa sem teto e come o orçamento de saída"
    )
    assert thinking.thinking_level is types.ThinkingLevel.LOW


@pytest.mark.asyncio
async def test_a_truncated_answer_is_reported_not_swallowed(fake_client, caplog):
    fake_client(_response('{"verd', types.FinishReason.MAX_TOKENS, thoughts=1151, output=45))

    with caplog.at_level(logging.WARNING):
        await llm.call_agent(
            system_prompt="s",
            user_content="u",
            max_output_tokens=1200,
            settings=_settings(),
        )

    assert "MAX_TOKENS" in caplog.text
    assert "1151" in caplog.text
    assert "1200" in caplog.text


@pytest.mark.asyncio
async def test_a_finished_answer_stays_quiet(fake_client, caplog):
    fake_client(_response("ok", types.FinishReason.STOP, thoughts=10, output=2))

    with caplog.at_level(logging.WARNING):
        text = await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert text == "ok"
    assert caplog.text == ""


@pytest.mark.asyncio
async def test_an_empty_answer_still_says_why(fake_client, caplog):
    response = types.GenerateContentResponse(candidates=[])

    fake_client(response)
    with caplog.at_level(logging.WARNING):
        assert await llm.call_agent(system_prompt="s", user_content="u", settings=_settings()) == ""

    assert "no candidates" in caplog.text
