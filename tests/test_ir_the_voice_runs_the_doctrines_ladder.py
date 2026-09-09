"""What the room actually puts on the wire for the Guide and the Validator.

These drive a whole turn with the Anthropic client faked, rather than with the usual
`call_agent` fake: the model id, the thinking mode, the effort and the cache breakpoint are
invisible at the `run_turn.call_agent` seam, so a test written there would go on passing if
the voice fell back to a flash model at low thinking — which is the regression this suite
exists to catch.
"""

from __future__ import annotations

import json
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


async def _a_turn(settings: Settings | None = None) -> None:
    await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="A fome chegou e eles partiram.",
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
