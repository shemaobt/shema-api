"""A Validator reply that cannot be a verdict takes the fail-safe line, read once.

Her app reads each draft once: a reply cut at its ceiling, unreadable, with an unknown verdict
or with a blank correction is never a verdict, and the team hears the line at once. These drive
a whole turn with the Anthropic client faked, because the stop reason and the number of times
the Validator was asked are invisible at the `room_agent().turn.call_agent` seam.
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
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.run_turn import run_turn

GUIDE = default_prompt(IRPromptKey.GUIDE)["prompt"]
VALIDATOR = default_prompt(IRPromptKey.VALIDATOR)["prompt"]
P = "P03"
PASS = json.dumps({"verdict": "pass", "issues": []})


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", anthropic_api_key="sk-ant-fake")


def _is_validator(call: dict[str, Any]) -> bool:
    system = call["system"]
    text = system if isinstance(system, str) else "".join(block["text"] for block in system)
    return "corrected_response" in text


class ScriptedValidator:
    """The Guide drafts the same words every time, and the Validator answers from a script.

    A script that runs out repeats its last reply, so a Validator asked again is counted
    rather than crashing the case.
    """

    def __init__(self, *replies: tuple[str, str]) -> None:
        self.replies = list(replies)
        self.calls: list[dict[str, Any]] = []

    @property
    def validator_calls(self) -> list[dict[str, Any]]:
        return [call for call in self.calls if _is_validator(call)]

    async def create(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(kwargs)
        if _is_validator(kwargs):
            asked = len(self.validator_calls)
            text, stop_reason = self.replies[min(asked, len(self.replies)) - 1]
        else:
            text, stop_reason = "Ensaiem essa parte entre vocês.", "end_turn"
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text=text)] if text else [],
            stop_reason=stop_reason,
            model=kwargs["model"],
            usage=SimpleNamespace(
                input_tokens=10,
                output_tokens=5,
                cache_read_input_tokens=0,
                cache_creation_input_tokens=0,
                cache_creation=None,
            ),
        )


@pytest.fixture
def validator_replies(monkeypatch: pytest.MonkeyPatch):
    def _install(*replies: tuple[str, str]) -> ScriptedValidator:
        messages = ScriptedValidator(*replies)
        monkeypatch.setattr(
            llm.anthropic,
            "AsyncAnthropic",
            lambda **options: SimpleNamespace(messages=messages, options=options),
        )
        return messages

    return _install


@pytest.fixture(autouse=True)
def _forget_which_rung_answered():
    llm._SETTLED.clear()
    yield
    llm._SETTLED.clear()


async def _a_turn():
    return await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="A fome chegou e eles partiram.",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=_settings(),
    )


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param(PASS, id="a verdict that looks whole"),
        pytest.param("", id="a reply the thinking ate whole"),
    ],
)
async def test_a_validator_reply_cut_at_its_ceiling_is_the_fail_safe_and_is_not_asked_again(
    validator_replies, reply: str
) -> None:
    messages = validator_replies((reply, "max_tokens"))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True, (
        "um veredito cortado no teto virava veredito, e a equipe ouvia um rascunho que o "
        "Validador nunca terminou de julgar"
    )
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert len(messages.validator_calls) == 1, (
        "o Validador era perguntado de novo sobre o mesmo rascunho depois de cortado no teto"
    )
    assert len(messages.calls) == 2, (
        "um rascunho, uma leitura, e nenhuma reescrita a pedido do corte"
    )


@pytest.mark.parametrize(
    "reply",
    [
        pytest.param("desculpe, não consigo julgar isso", id="loose prose"),
        pytest.param(json.dumps({"ok": True}), id="an object with no verdict"),
        pytest.param(
            json.dumps({"verdict": "correct", "corrected_response": "  ", "issues": []}),
            id="a correction that is blank",
        ),
    ],
)
async def test_a_validator_reply_that_cannot_be_read_is_one_reading_and_the_fail_safe(
    validator_replies, reply: str
) -> None:
    messages = validator_replies((reply, "end_turn"), (PASS, "end_turn"))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert len(messages.validator_calls) == 1, (
        "uma resposta ilegível do Validador era perguntada de novo, e a equipe só ouvia a linha "
        "de segurança quando a segunda leitura também falhava; a leitura de um rascunho é uma"
    )
    assert len(messages.calls) == 2
