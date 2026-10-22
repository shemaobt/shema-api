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
DRAFT = "Ensaiem essa parte entre vocês."


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
        self.guide_stop_reason = "end_turn"
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
            text, stop_reason = DRAFT, self.guide_stop_reason
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


@pytest.mark.parametrize(
    "verdict",
    [
        pytest.param("approve", id="a word she never named"),
        pytest.param(None, id="no value at all"),
        pytest.param(["pass"], id="a list where a word belongs"),
    ],
)
async def test_a_verdict_she_never_named_is_the_fail_safe_and_not_a_redraft(
    validator_replies, verdict: Any
) -> None:
    reply = json.dumps({"verdict": verdict, "issues": []})
    messages = validator_replies((reply, "end_turn"), (PASS, "end_turn"))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert outcome.redrafts == 0, (
        "um veredito desconhecido era tratado como regenerate e gastava reescritas do Guia, "
        "quando o Validador nem chegou a julgar o rascunho"
    )
    assert len(messages.calls) == 2, "um rascunho e uma leitura, nada além disso"


async def test_a_guide_draft_cut_at_its_ceiling_still_goes_to_the_validator_as_it_stands(
    validator_replies,
) -> None:
    messages = validator_replies((PASS, "end_turn"))
    messages.guide_stop_reason = "max_tokens"

    outcome = await _a_turn()

    assert outcome.used_fail_safe is False, (
        "um rascunho cortado no teto virava linha de segurança antes de o Validador ver o que "
        "havia; ele só é a linha de segurança quando não sobra texto nenhum"
    )
    assert outcome.speech == DRAFT
    (validator,) = messages.validator_calls
    assert DRAFT in "".join(block["text"] for block in validator["system"]), (
        "o Validador julga o texto como ele ficou, cortado ou não"
    )
