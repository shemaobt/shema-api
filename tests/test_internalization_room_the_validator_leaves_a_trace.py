"""What the Validator's own reply leaves behind when it cannot be used.

Same idea as the ENG-719 fix on the Analyst's side (`back_translation._refused`, a sibling
change not yet on `main` as of this writing): the night of 2026-09-01 the room fell to the
family-A fail-safe and nobody could say why, because nothing here kept what the Validator
actually answered. Every exit that discards a Validator reply — or a Guide draft the room's
own gates reject — now leaves exactly one WARNING record behind it, on this module's own
logger, carrying the session, the attempt, and the condition that refused it.

`test_a_failed_call_is_logged_without_repeating_what_the_team_said` in
`test_internalization_room_model_failure.py` is this file's twin for the exception path
and for the promise that the team's own words never reach this logger; it is not edited
here.
"""

import logging
from typing import Any

import pytest

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.fail_safe import FailSafe, utterances
from app.services.internalization_room.run_turn import MAX_REDRAFTS, run_turn
from tests.turn_harness import (
    GUIDE,
    VALIDATOR,
    FakeAgent,
    P,
    settings,
    the_agent_answers,
)


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    """The fake in place of the model, for the cases in this module."""

    def _install(agent: FakeAgent) -> FakeAgent:
        return the_agent_answers(monkeypatch, agent)

    return _install


LOGGER_NAME = "app.services.internalization_room.validated_turn"
BRIDGE_LANGUAGE_LOGGER_NAME = "app.services.internalization_room.bridge_language"
TEAM_ANSWER = "Noemi voltou para Belém com Rute no tempo da colheita"


def _refusal_records(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """Only the records this fix adds: this module's logger, and carrying a condition.

    The exhaustion summary at the end of a redraft loop is also a WARNING on this same
    logger, but it names no condition — filtering on the field keeps it out without having
    to know its wording.
    """
    return [
        record
        for record in caplog.records
        if record.name == LOGGER_NAME
        and record.levelno == logging.WARNING
        and "condition" in record.__dict__
    ]


async def _a_turn(session_id: str, **overrides: Any):
    kwargs: dict[str, Any] = {
        "session_id": session_id,
        "session_language": "Portuguese",
        "language_code": "pt",
        "transcript": "alguma coisa",
        "coverage_state": initial_state(P),
        "messages": [],
        "guide_prompt": GUIDE,
        "validator_prompt": VALIDATOR,
        "pericope_num": P,
        "settings": settings(),
    }
    kwargs.update(overrides)
    return await run_turn(**kwargs)


async def test_a_validator_answering_loose_text_twice_leaves_two_traces_on_one_draft(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    """Both readings are of the first draft, so both traces name attempt 1.

    Three traces on attempts 1, 2 and 3 was the shape when an unreadable reply cost a
    redraft; a reply the room cannot read is now read again before anything is redrawn.
    """

    class Garbage(FakeAgent):
        async def __call__(self, *, system_prompt: str, user_content: str, **kwargs: Any) -> str:
            is_validator = "corrected_response" in system_prompt
            self.calls.append("validator" if is_validator else "guide")
            return "desculpe, não consigo" if is_validator else "rascunho"

    patch_agent(Garbage(verdicts=[]))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-1")

    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")

    refusals = _refusal_records(caplog)
    assert len(refusals) == 2
    for record in refusals:
        assert record.__dict__["attempt"] == 1
        assert record.__dict__["session_id"] == "sessao-1"
        assert "json" in record.__dict__["condition"].lower()
        assert "desculpe, não consigo" in record.getMessage()


async def test_json_without_a_verdict_key_also_leaves_a_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"ok": True}] * 2))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-2")

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 2
    for record in refusals:
        assert "verdict" in record.__dict__["condition"].lower()
        assert '"ok": true' in record.getMessage().lower()


async def test_a_regenerate_verdict_leaves_the_whole_reply(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(
        FakeAgent(
            verdicts=[
                {
                    "verdict": "regenerate",
                    "issues": [{"problem": "claims_to_see_the_screen"}],
                }
            ]
            * (MAX_REDRAFTS + 1)
        )
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-3")

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert "regenerate" in record.__dict__["condition"].lower()
        assert "claims_to_see_the_screen" in record.getMessage()


async def test_a_correct_verdict_with_no_text_leaves_a_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"verdict": "correct", "corrected_response": "  "}] * 2))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-4")

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 2
    for record in refusals:
        assert "correct" in record.__dict__["condition"].lower()
        assert "empty" in record.__dict__["condition"].lower()
        assert "corrected_response" in record.getMessage()


async def test_a_draft_out_of_the_bridge_language_leaves_the_condition_not_the_words(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    """The counterpart of the policy test, on the recusal path instead of the exception one.

    The draft is the Guide's, and the Guide can echo the team — so only the condition and a
    count of characters are allowed onto this logger, never the drafted words themselves.
    """
    draft = "Tell me what you think happens next in this part of the story."
    patch_agent(
        FakeAgent(
            verdicts=[{"verdict": "pass", "issues": []}] * (MAX_REDRAFTS + 1),
            drafts=[draft] * (MAX_REDRAFTS + 1),
        )
    )

    with (
        caplog.at_level(logging.WARNING, logger=LOGGER_NAME),
        caplog.at_level(logging.WARNING, logger=BRIDGE_LANGUAGE_LOGGER_NAME),
    ):
        outcome = await _a_turn("sessao-5")

    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.UNREPAIRABLE, "pt")

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert "off_bridge_language" in record.__dict__["condition"]
        assert draft not in record.getMessage()
        for value in record.__dict__.values():
            assert draft not in str(value)
    assert draft not in caplog.text


async def test_the_teams_own_words_never_reach_this_log_on_the_recusal_path(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    """Sibling of `test_a_failed_call_is_logged_without_repeating_what_the_team_said`.

    That test covers the exception exit; this one covers the ordinary recusal exit, with a
    Guide draft that quotes the team's turn and a Validator that never does.
    """
    patch_agent(
        FakeAgent(
            verdicts=[
                {"verdict": "regenerate", "issues": [{"problem": "off_topic"}]},
            ]
            * (MAX_REDRAFTS + 1),
            drafts=[f"Vocês disseram: {TEAM_ANSWER}"] * (MAX_REDRAFTS + 1),
        )
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-6", transcript=TEAM_ANSWER)

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    assert TEAM_ANSWER not in caplog.text


async def test_every_refusal_carries_the_sessions_own_id(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(
        FakeAgent(
            verdicts=[
                {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]},
            ]
            * (MAX_REDRAFTS + 1)
        )
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await _a_turn("a-verdadeira-sessao-7")

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert record.__dict__["session_id"] == "a-verdadeira-sessao-7"
        assert record.__dict__["session_id"] != "?"


async def test_a_passing_verdict_leaves_no_refusal_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=["Fala normal."]))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-8")

    assert outcome.used_fail_safe is False
    assert _refusal_records(caplog) == []
