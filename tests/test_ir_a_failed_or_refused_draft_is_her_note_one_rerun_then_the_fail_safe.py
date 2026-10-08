from __future__ import annotations

import pytest

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

REGENERATE = {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
PASS = {"verdict": "pass", "issues": []}


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
        settings=settings(),
    )


@pytest.mark.parametrize(
    ("drafts", "verdicts", "calls"),
    [
        pytest.param([""] * 3, [PASS] * 3, ["guide"], id="the first draft"),
        pytest.param(["[[CENA]]"] * 3, [PASS] * 3, ["guide"], id="a draft that was only the mark"),
        pytest.param(
            ["rascunho", "", ""],
            [REGENERATE, PASS, PASS],
            ["guide", "validator", "guide"],
            id="the redraft",
        ),
    ],
)
async def test_an_empty_draft_is_the_fail_safe_at_once_and_never_reaches_the_validator(
    monkeypatch: pytest.MonkeyPatch, drafts: list[str], verdicts: list[dict], calls: list[str]
) -> None:
    agent = the_agent_answers(monkeypatch, FakeAgent(verdicts=verdicts, drafts=drafts))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True, (
        "um rascunho vazio ia ao Validador, que podia aprová-lo como fala vazia ou escrever "
        "uma correção no lugar do Guia"
    )
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")
    assert agent.calls == calls, (
        "o rascunho vazio ainda custava uma leitura do Validador e outra reescrita antes da "
        "linha de segurança que o app dela dá na hora"
    )
    assert outcome.draft == ""
    assert outcome.verdict == ""
