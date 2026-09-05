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
from tests.test_internalization_room_turn import (
    GUIDE,
    VALIDATOR,
    FakeAgent,
    P,
    _settings,
    patch_agent,
)

#: Re-exported so pytest resolves it as a fixture here too — `patch_agent` is a fixture
#: function, not a side-effect import, so silencing the unused-import warning alone (this
#: codebase's usual idiom for an unused import) still leaves every test parameter of the
#: same name looking like a redefinition of it to ruff. `__all__` marks the name genuinely
#: used.
__all__ = ["patch_agent"]

LOGGER_NAME = "app.services.internalization_room.run_turn"
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
        "settings": _settings(),
    }
    kwargs.update(overrides)
    return await run_turn(**kwargs)


@pytest.mark.asyncio
async def test_a_validator_answering_loose_text_three_times_leaves_three_traces(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
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
    assert len(refusals) == 3
    for attempt, record in enumerate(refusals, start=1):
        assert record.__dict__["attempt"] == attempt
        assert record.__dict__["session_id"] == "sessao-1"
        assert "json" in record.__dict__["condition"].lower()
        assert "desculpe, não consigo" in record.getMessage()


@pytest.mark.asyncio
async def test_json_without_a_verdict_key_also_leaves_a_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"ok": True}] * (MAX_REDRAFTS + 1)))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-2")

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert "verdict" in record.__dict__["condition"].lower()
        assert '"ok": true' in record.getMessage().lower()


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_a_correct_verdict_with_no_text_leaves_a_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(
        FakeAgent(
            verdicts=[{"verdict": "correct", "corrected_response": "  "}] * (MAX_REDRAFTS + 1)
        )
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-4")

    assert outcome.used_fail_safe is True

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert "correct" in record.__dict__["condition"].lower()
        assert "empty" in record.__dict__["condition"].lower()
        assert "corrected_response" in record.getMessage()


@pytest.mark.asyncio
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

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-5")

    assert outcome.used_fail_safe is True
    assert outcome.speech in utterances(FailSafe.OFF_BRIDGE_LANGUAGE, "pt")

    refusals = _refusal_records(caplog)
    assert len(refusals) == 3
    for record in refusals:
        assert "off_bridge_language" in record.__dict__["condition"]
        assert draft not in record.getMessage()
        for value in record.__dict__.values():
            assert draft not in str(value)


@pytest.mark.asyncio
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


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_a_passing_verdict_leaves_no_refusal_trace(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=["Fala normal."]))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        outcome = await _a_turn("sessao-8")

    assert outcome.used_fail_safe is False
    assert _refusal_records(caplog) == []
