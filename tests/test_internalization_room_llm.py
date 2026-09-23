import asyncio
import logging
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.core.config import Settings
from app.core.exceptions import UpstreamServiceError
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
    cache_creation: SimpleNamespace | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason,
        model="claude-fable-5-1",
        usage=SimpleNamespace(
            input_tokens=10,
            output_tokens=output,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=(
                cache_creation.ephemeral_5m_input_tokens + cache_creation.ephemeral_1h_input_tokens
                if cache_creation
                else 0
            ),
            cache_creation=cache_creation,
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


class RefusingMessages:
    """A first rung that turns the request away at the door, and a second that answers."""

    def __init__(self) -> None:
        self.asked: list[str] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.asked.append(kwargs["model"])
        if kwargs["model"] == "claude-fable-5-1":
            reply = _reply("", stop_reason="refusal")
            reply.content = []
            return reply
        return _reply("ok")


async def test_a_rung_that_refuses_outright_hands_the_request_to_the_next(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = RefusingMessages()
    monkeypatch.setattr(
        llm.anthropic,
        "AsyncAnthropic",
        lambda **options: SimpleNamespace(messages=messages, options=options),
    )

    text = await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert messages.asked == ["claude-fable-5-1", "claude-opus-5"], (
        "um degrau que recusava a pedido inteiro (stop_reason refusal, zero tokens) era "
        "devolvido como resposta vazia; a verificação da correção falhava cinco vezes e a "
        "sessão pedia uma pessoa por um turno em que a equipe acertou tudo"
    )
    assert text == "ok"
    assert llm._SETTLED == {}, (
        "uma recusa é sobre este pedido, não sobre a chave: o degrau de cima continua sendo "
        "o primeiro a ser perguntado no próximo turno"
    )


async def test_a_rate_limit_keeps_the_rung_it_is_on(ladder_client) -> None:
    messages = ladder_client("nunca", anthropic.RateLimitError)

    with pytest.raises(UpstreamServiceError):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert messages.asked == ["claude-fable-5-1"], (
        "um limite de taxa gastava a escada inteira e a sessão seguia num modelo mais fraco "
        "por um minuto de pressa; a escada é sobre o que a chave PODE usar, não sobre pressa"
    )


async def test_the_conversation_travels_as_turns_with_the_new_utterance_last(fake_client):
    """The Guide is handed the exchange it lived, not a block of text describing it.

    Nine exchanges in, the Guide greeted the team and introduced itself: everything older
    than six messages had never been in its prompt. The room now sends what was said as the
    turns it was said in, and `user_content` is the last of them.
    """
    holder = fake_client(_reply("ok"))

    await llm.call_agent(
        system_prompt="s",
        user_content="e a fome?",
        conversation=[
            {"role": "assistant", "text": "Sou o guia."},
            {"role": "user", "text": "a fome levou eles embora"},
            {"role": "assistant", "text": "Isso mesmo."},
        ],
        settings=_settings(),
    )

    assert holder["client"].messages.kwargs["messages"] == [
        {"role": "assistant", "content": "Sou o guia."},
        {"role": "user", "content": "a fome levou eles embora"},
        {"role": "assistant", "content": "Isso mesmo."},
        {"role": "user", "content": "e a fome?"},
    ]


async def test_a_caller_that_names_no_conversation_still_sends_one_user_message(fake_client):
    """The analyst, the classifier and the two back-translation callers share this function."""
    holder = fake_client(_reply("ok"))

    await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert holder["client"].messages.kwargs["messages"] == [{"role": "user", "content": "u"}]


async def test_the_guide_and_the_validator_prefix_cache_for_an_hour_by_default(fake_client):
    holder = fake_client(_reply("ok"))

    for role in ("guide", "validator"):
        await llm.call_agent(
            system_prompt=f"map{llm.CACHE_BREAK}turn",
            user_content="u",
            role=role,
            settings=_settings(),
        )

        assert holder["client"].messages.kwargs["system"][0]["cache_control"] == {
            "type": "ephemeral",
            "ttl": "1h",
        }, (
            f"o prefixo do {role} caía a cada 5 minutos e a pausa de ensaio da equipe relia "
            f"~16k/14k tokens do zero na volta"
        )


async def test_the_judge_and_the_classifier_stay_on_the_five_minute_cache(fake_client):
    holder = fake_client(_reply("ok"))

    for role in ("judge", "analyst", "correction check", "classifier", "?"):
        await llm.call_agent(
            system_prompt=f"map{llm.CACHE_BREAK}turn",
            user_content="u",
            role=role,
            settings=_settings(),
        )

        assert "ttl" not in holder["client"].messages.kwargs["system"][0]["cache_control"], (
            f"o {role} não fica no caminho da voz, e uma escrita de 1h custa o dobro de uma "
            f"de 5 min sem nenhum ganho — a doutrina só cobre a voz"
        )


async def test_the_hour_cache_reverts_to_five_minutes_through_a_setting(fake_client):
    holder = fake_client(_reply("ok"))

    await llm.call_agent(
        system_prompt=f"map{llm.CACHE_BREAK}turn",
        user_content="u",
        role="guide",
        settings=_settings(internalization_room_voice_cache_ttl=""),
    )

    assert holder["client"].messages.kwargs["system"][0]["cache_control"] == {
        "type": "ephemeral"
    }, (
        "um deployment que precisasse voltar aos 5 minutos não tinha como, sem esperar um "
        "novo deploy do código"
    )


async def test_the_usage_line_says_which_cache_lifetime_each_written_token_bought(
    fake_client, caplog
):
    fake_client(
        _reply(
            "ok",
            cache_creation=SimpleNamespace(
                ephemeral_5m_input_tokens=3_000, ephemeral_1h_input_tokens=90_000
            ),
        )
    )

    with caplog.at_level(logging.INFO):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert "cache_write=93000 cache_write_5m=3000 cache_write_1h=90000 " in caplog.text, (
        "a escrita no cache era um número só, e a de 1 hora custa 2x o input contra 1,25x"
    )


async def test_an_hour_of_cache_write_costs_twice_a_five_minute_one(fake_client, caplog):
    fake_client(
        _reply(
            "ok",
            cache_creation=SimpleNamespace(
                ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=1_000_000
            ),
        )
    )

    with caplog.at_level(logging.INFO):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    record = next(r for r in caplog.records if getattr(r, "cost_usd", None) is not None)
    assert record.cost_usd == pytest.approx(20.0001), (
        "o milhão de tokens de escrita de 1h era cobrado ao preço de 5 min (US$ 12,50 no "
        "Fable 5.1), e o total do turno saía US$ 7,50 abaixo do que ele de fato custou"
    )


async def test_a_call_that_wrote_nothing_to_the_cache_says_zero_for_both_lifetimes(
    fake_client, caplog
):
    fake_client(_reply("ok"))

    with caplog.at_level(logging.INFO):
        await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    assert "cache_write=0 cache_write_5m=0 cache_write_1h=0 " in caplog.text


@pytest.fixture
def counted_builds(monkeypatch: pytest.MonkeyPatch) -> list[FakeClient]:
    built: list[FakeClient] = []

    def _build(**options: Any) -> FakeClient:
        built.append(FakeClient(_reply("ok"), **options))
        return built[-1]

    monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
    return built


async def test_two_calls_on_one_event_loop_share_one_client_instead_of_one_each(
    counted_builds: list[FakeClient],
) -> None:
    await llm.call_agent(system_prompt="s", user_content="u", role="guide", settings=_settings())
    await llm.call_agent(
        system_prompt="s", user_content="u", role="validator", settings=_settings()
    )

    assert len(counted_builds) == 1, (
        "cada chamada do Guia e do Validador abria um cliente novo, com handshake TLS e "
        "contexto SSL, enquanto a equipe esperava a resposta"
    )


def test_a_second_event_loop_builds_its_own_client_rather_than_borrowing_one(
    counted_builds: list[FakeClient],
) -> None:
    async def _ask() -> str:
        return await llm.call_agent(system_prompt="s", user_content="u", settings=_settings())

    for _ in range(2):
        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_ask())
        finally:
            loop.close()

    assert len(counted_builds) == 2, (
        "um cliente preso a um loop fechado era entregue a outro, e a conexão dele não "
        "responde fora do loop que a abriu"
    )
