"""A prepared opening's own [llm-turn] line names the pericope it was written for.

The night of 21/09/2026 (ENG-968) and again at the gate behind ENG-1107, a session's log
carried two `[llm-turn]` lines under the same session id and both were read as "the opening
ran twice." The second was `prepare_opening`'s own background run for the passage the team
had not entered yet — it shares the panorama's own session id, and nothing on the line said
it was a different turn for a different pericope. This is that line's own trace, the same
idea as `test_internalization_room_the_validator_leaves_a_trace.py`.
"""

import logging
from typing import Any

import pytest

from app.services.internalization_room.coverage import initial_state
from app.services.internalization_room.run_turn import run_turn
from tests.turn_harness import GUIDE, VALIDATOR, FakeAgent, P, settings, the_agent_answers

LOGGER_NAME = "app.services.internalization_room.validated_turn"


@pytest.fixture
def patch_agent(monkeypatch: pytest.MonkeyPatch):
    """The fake in place of the model, for the cases in this module."""

    def _install(agent: FakeAgent) -> FakeAgent:
        return the_agent_answers(monkeypatch, agent)

    return _install


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


def _the_turn_line(caplog: pytest.LogCaptureFixture) -> logging.LogRecord:
    lines = [
        record
        for record in caplog.records
        if record.name == LOGGER_NAME and record.getMessage().startswith("[llm-turn]")
    ]
    assert len(lines) == 1
    return lines[0]


async def test_a_prepared_openings_turn_line_names_the_pericope_it_is_for(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=["Fala normal."]))

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _a_turn(
            "panorama-1", opening=True, transcript="", prepared_pericope="P01"
        )

    record = _the_turn_line(caplog)
    assert "prepared=P01" in record.getMessage()
    assert record.__dict__["prepared_pericope"] == "P01"


async def test_a_live_turns_line_never_names_a_pericope_as_prepared(
    patch_agent, caplog: pytest.LogCaptureFixture
) -> None:
    patch_agent(FakeAgent(verdicts=[{"verdict": "pass", "issues": []}], drafts=["Fala normal."]))

    with caplog.at_level(logging.INFO, logger=LOGGER_NAME):
        await _a_turn("sessao-1")

    record = _the_turn_line(caplog)
    assert "prepared=" not in record.getMessage()
    assert record.__dict__["prepared_pericope"] is None
