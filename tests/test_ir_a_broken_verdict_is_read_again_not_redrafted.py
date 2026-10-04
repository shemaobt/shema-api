"""What a Validator reply the room cannot read costs the team.

The Validator is asked for a bare JSON object. When it answered with prose around the
object, or with prose alone, the room read that as `regenerate`, spent a Guide redraft on
a verdict nobody could read, and on the next unreadable reply spent the last one — a team
that did nothing wrong heard the family-A line after three model round-trips. Her policy
names this case as its own: the draft is validated again, and only when the second
reading also fails does a fixed line answer, with the Guide's redrafts unspent.
"""

import json
from typing import Any

import pytest

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.run_turn import run_turn
from app.services.internalization_room.validator_reply import _parse_verdict
from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

PASS = {"verdict": "pass", "issues": []}
PROSE = "desculpe, não consigo"


class ScriptedValidator:
    """The Guide always drafts the same words; the Validator reads from a script."""

    def __init__(self, replies: list[str]) -> None:
        self.replies = replies
        self.calls: list[str] = []
        self.judged: list[str] = []

    async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
        if "corrected_response" not in system_prompt:
            self.calls.append("guide")
            return "rascunho"
        self.calls.append("validator")
        self.judged.append(system_prompt)
        return self.replies[len(self.judged) - 1]


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    """The fake in place of the model, for the cases in this module."""

    def _install(agent: Any) -> Any:
        return the_agent_answers(monkeypatch, agent)

    return _install


async def _a_turn():
    return await run_turn(
        session_language="Portuguese",
        language_code="pt",
        transcript="alguma coisa",
        coverage_state=initial_state(P),
        messages=[],
        guide_prompt=GUIDE,
        validator_prompt=VALIDATOR,
        pericope_num=P,
        settings=settings(),
    )


async def test_a_verdict_unreadable_twice_is_line_a_with_both_redrafts_unspent(
    patch_agent,
) -> None:
    agent = patch_agent(ScriptedValidator([PROSE, PROSE]))

    outcome = await _a_turn()

    assert agent.calls == ["guide", "validator", "validator"]
    assert outcome.redrafts == 0
    assert outcome.used_fail_safe is True
    assert outcome.fixed_line.startswith("A")
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")


async def test_the_second_reading_judges_the_same_draft_and_its_verdict_stands(
    patch_agent,
) -> None:
    agent = patch_agent(ScriptedValidator([PROSE, json.dumps(PASS)]))

    outcome = await _a_turn()

    assert agent.calls == ["guide", "validator", "validator"]
    assert agent.judged[0] == agent.judged[1]
    assert outcome.speech == "rascunho"
    assert outcome.redrafts == 0
    assert outcome.used_fail_safe is False


def test_a_verdict_inside_a_code_fence_is_read() -> None:
    verdict, refusal = _parse_verdict('```json\n{"verdict": "pass", "issues": []}\n```')

    assert refusal is None
    assert verdict == PASS


def test_a_verdict_wrapped_in_prose_is_read() -> None:
    verdict, refusal = _parse_verdict(
        'Here is my verdict: {"verdict": "pass", "issues": []} — hope that helps.'
    )

    assert refusal is None
    assert verdict == PASS


def test_a_reply_with_no_object_in_it_is_refused_and_is_not_a_regenerate() -> None:
    verdict, refusal = _parse_verdict("desculpe, não consigo")

    assert refusal is not None
    assert verdict.get("verdict") != "regenerate"
    assert verdict.get("issues", []) == []


def test_a_correction_with_nothing_to_say_is_refused_and_is_not_a_regenerate() -> None:
    verdict, refusal = _parse_verdict('{"verdict": "correct", "corrected_response": "  "}')

    assert refusal is not None
    assert verdict.get("verdict") != "regenerate"


async def test_a_firing_keeps_the_last_draft_and_the_verdict_that_refused_it(
    patch_agent,
) -> None:
    regenerate = {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}
    patch_agent(FakeAgent(verdicts=[regenerate] * 3, drafts=["um", "dois", "três"]))

    outcome = await _a_turn()

    assert outcome.used_fail_safe is True
    assert outcome.draft == "três"
    assert outcome.verdict == "regenerate"
    assert outcome.issues == [{"problem": "imported_knowledge"}]


async def test_a_firing_on_an_unreadable_reply_keeps_the_draft_and_no_verdict(
    patch_agent,
) -> None:
    patch_agent(ScriptedValidator([PROSE, PROSE]))

    outcome = await _a_turn()

    assert outcome.draft == "rascunho"
    assert outcome.verdict == ""


async def test_a_voiced_turn_keeps_the_verdict_that_let_it_through(patch_agent) -> None:
    patch_agent(
        FakeAgent(
            verdicts=[{"verdict": "correct", "issues": [], "corrected_response": "mendado"}],
            drafts=["torto"],
        )
    )

    outcome = await _a_turn()

    assert outcome.speech == "mendado"
    assert outcome.draft == "torto"
    assert outcome.verdict == "correct"
