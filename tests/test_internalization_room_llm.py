import logging
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
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


async def test_an_identity_bound_key_names_the_workspace_it_acts_in(fake_client) -> None:
    holder = fake_client(_reply("ok"))

    await llm.call_agent(
        system_prompt="s",
        user_content="u",
        settings=_settings(anthropic_workspace_id="wrkspc-de-teste"),
    )

    headers = holder["client"].options["default_headers"]
    assert headers["anthropic-workspace-id"] == "wrkspc-de-teste", (
        "a chave do Console é ligada a uma pessoa e a API responde 400 'not scoped to a "
        "workspace' sem esse cabeçalho: a sala inteira ficava muda em produção"
    )


async def test_a_classic_key_sends_no_workspace_header_at_all(fake_client) -> None:
    holder = fake_client(_reply("ok"))

    await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert holder["client"].options["default_headers"] is None, (
        "um cabeçalho de workspace vazio viaja em toda chamada de uma chave clássica, que "
        "não tem workspace nenhum para nomear"
    )


def _refusal_response() -> httpx2.Response:
    """A real response object, because the SDK's errors read `response.request` on the way up."""
    return httpx2.Response(
        status_code=404, request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    )


class LadderMessages:
    """A key that cannot use the rungs above `usable`, and answers on the first it can."""

    def __init__(self, usable: str, refusal: type[Exception]):
        self.usable = usable
        self.refusal = refusal
        self.asked: list[str] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.asked.append(kwargs["model"])
        if kwargs["model"] != self.usable:
            raise self.refusal("nope", response=_refusal_response(), body=None)
        return _reply("ok")


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    """The settled rung outlives a test, so a step-down here would steer a later file."""
    llm._SETTLED.clear()
    yield
    llm._SETTLED.clear()


@pytest.fixture
def ladder_client(monkeypatch: pytest.MonkeyPatch):
    def _install(usable: str, refusal: type[Exception]) -> LadderMessages:
        messages = LadderMessages(usable, refusal)
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **options: SimpleNamespace(messages=messages, options=options),
        )
        return messages

    return _install


async def test_a_model_this_key_cannot_use_steps_down_to_the_next_rung(ladder_client) -> None:
    messages = ladder_client("claude-opus-5", anthropic.NotFoundError)

    text = await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert messages.asked == ["claude-fable-5-1", "claude-opus-5"], (
        "uma chave sem acesso ao topo da escada derrubava o turno inteiro em vez de descer "
        "um degrau, e a sala respondia com linha enlatada por uma questão de permissão"
    )
    assert text == "ok"


async def test_a_rate_limit_keeps_the_rung_it_is_on(ladder_client) -> None:
    messages = ladder_client("nunca", anthropic.RateLimitError)

    with pytest.raises(anthropic.RateLimitError):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert messages.asked == ["claude-fable-5-1"], (
        "um limite de taxa gastava a escada inteira e a sessão seguia num modelo mais fraco "
        "por um minuto de pressa; a escada é sobre o que a chave PODE usar, não sobre pressa"
    )
