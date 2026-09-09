"""What the room actually puts on the wire for the Guide and the Validator.

These drive a whole turn with the Anthropic client faked, rather than with the usual
`call_agent` fake: the model id, the thinking mode, the effort and the cache breakpoint are
invisible at the `run_turn.call_agent` seam, so a test written there would go on passing if
the voice fell back to a flash model at low thinking — which is the regression this suite
exists to catch.
"""

from __future__ import annotations

import json
import logging
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import Settings
from app.db.models.internalization_room import IRPromptKey
from app.services.internalization_room import llm
from app.services.internalization_room._default_prompts import default_prompt
from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"


def _settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "database_url": "sqlite+aiosqlite:///./test.db",
        "anthropic_api_key": "sk-ant-fake",
    }
    base.update(overrides)
    return Settings(**base)


def _system_text(call: dict[str, Any]) -> str:
    system = call["system"]
    if isinstance(system, str):
        return system
    return "".join(block["text"] for block in system)


def _is_validator(call: dict[str, Any]) -> bool:
    return "corrected_response" in _system_text(call)


class RecordingMessages:
    def __init__(self, draft: str, verdict: dict[str, Any]):
        self.draft = draft
        self.verdict = verdict
        self.calls: list[dict[str, Any]] = []
        self.built: list[Any] = []

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        spoken = json.dumps(self.verdict) if _is_validator(kwargs) else self.draft
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=spoken)],
            stop_reason="end_turn",
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
            ),
        )


class RecordingClient:
    """One recorder shared by every client the room builds.

    `call_agent` constructs a client per call, so a recorder owned by the client would keep
    only the last call of a turn and a two-call assertion would silently see one.
    """

    def __init__(self, messages: RecordingMessages, **options: Any):
        self.messages = messages
        self.options = options


@pytest.fixture
def recording_client(monkeypatch: pytest.MonkeyPatch):
    def _install(
        draft: str = "Ensaiem essa parte entre vocês.",
        verdict: dict[str, Any] | None = None,
    ) -> RecordingMessages:
        messages = RecordingMessages(draft, verdict or {"verdict": "pass", "issues": []})
        built: list[RecordingClient] = []

        def _build(**options: Any) -> RecordingClient:
            client = RecordingClient(messages, **options)
            built.append(client)
            return client

        monkeypatch.setattr(llm.anthropic, "AsyncAnthropic", _build)
        messages.built = built
        return messages

    return _install


async def _a_turn(
    settings: Settings | None = None,
    transcript: str = "A fome chegou e eles partiram.",
) -> None:
    await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript=transcript,
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings or _settings(),
    )


async def test_the_guide_and_the_validator_both_think_adaptively_at_high_effort(
    recording_client,
) -> None:
    messages = recording_client()

    await _a_turn()

    calls = messages.calls
    assert len(calls) == 2, "um turno é o rascunho do Guia e o julgamento do Validador"
    for call in calls:
        role = "Validador" if _is_validator(call) else "Guia"
        assert call["thinking"] == {"type": "adaptive"}, (
            f"o {role} rodava em ThinkingLevel.LOW, que a doutrina proíbe no caminho da voz"
        )
        assert call["output_config"]["effort"] == "high", (
            f"o {role} rodava sem esforço declarado e o padrão do provedor decidia por ele"
        )
        assert call["max_tokens"] == 4096, (
            f"o teto de saída do {role} cortava a resposta inteira ao meio da frase"
        )


async def test_the_map_that_repeats_every_turn_rides_in_one_cached_block(
    recording_client,
) -> None:
    messages = recording_client()

    await _a_turn(transcript="A fome chegou e eles partiram.")
    await _a_turn(transcript="Quem era Noemi?")

    for role, calls in (
        ("Guia", [c for c in messages.calls if not _is_validator(c)]),
        ("Validador", [c for c in messages.calls if _is_validator(c)]),
    ):
        first, second = (call["system"] for call in calls)
        assert isinstance(first, list), (
            f"o system do {role} ia como um texto só, sem fronteira entre o que repete e o "
            f"que muda, e o cache não tem onde ser marcado"
        )
        assert first[0]["cache_control"] == {"type": "ephemeral"}, (
            f"o prefixo do {role} ia inteiro a cada turno e o mapa era relido do zero"
        )
        assert first[0]["text"] == second[0]["text"], (
            f"o prefixo do {role} mudava de bytes entre turnos, então nada era servido do cache"
        )
        assert "cache_control" not in first[1], (
            f"o que varia por turno no {role} entrava no cache e escrevia uma entrada por turno"
        )
        assert "Meaning Map" in first[0]["text"], (
            f"o bloco cacheado do {role} não continha o mapa, que é o volume que paga o cache"
        )


async def test_no_bead_is_classified_while_the_team_waits_for_an_answer(
    recording_client,
) -> None:
    messages = recording_client()

    await _a_turn()

    spoken_on = [call["model"] for call in messages.calls]
    assert "claude-sonnet-5" not in spoken_on, (
        "o classificador entrou no turno e a equipe esperou por uma chamada que só mexe "
        "nas contas do colar; no runner das sessões-ouro esse turno mediu 322 s"
    )


async def test_every_turn_leaves_behind_what_it_cost_and_how_long_it_took(
    recording_client, caplog
) -> None:
    recording_client()

    with caplog.at_level(logging.INFO):
        await _a_turn()

    calls = [r for r in caplog.records if getattr(r, "cache_read_tokens", None) is not None]
    assert len(calls) == 2, (
        "o piloto não tinha como saber quanto do mapa veio do cache, então a conta da sessão "
        "era um palpite e o cache podia estar desligado sem ninguém notar"
    )
    assert {r.rung for r in calls} == {"claude-fable-5-1"}
    turn = next(r for r in caplog.records if getattr(r, "turn_ms", None) is not None)
    assert turn.turn_ms >= 0, (
        "a latência do turno inteiro não era medida em lugar nenhum, e 10 s e 56 s eram a "
        "mesma coisa para quem lesse o log"
    )
