"""What a prepared opening leaves behind when it never reaches a session.

Same idea as `test_internalization_room_the_validator_leaves_a_trace.py` (ENG-719's fix on
the Analyst side): a background preparation the Validator refuses used to vanish into an
`INFO` line with no session id, no pericope, and no reason, and the team fell into a live
opening turn with nothing anywhere saying why (ENG-927). A transport error reaching
`prepare_opening`'s own outer guard had the same problem the other way — it was already
logged, but at `ERROR` and without the session id next to the pericope it did carry.
"""

import logging

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.internalization_room import IRSession, IRSessionStatus
from app.services.internalization_room import prepare_opening as prepare_opening_module
from app.services.internalization_room.prepare_opening import prepare_opening
from app.services.internalization_room.run_turn import TurnOutcome
from tests.turn_harness import FakeAgent, the_agent_answers

LOGGER_NAME = "app.services.internalization_room.prepare_opening"
PASSAGE_TEXT = "Uma família sai de Belém por falta de comida."
REGENERATE = {"verdict": "regenerate", "issues": [{"problem": "imported_knowledge"}]}


def _panorama(**over: object) -> IRSession:
    fields: dict[str, object] = {
        "id": "panorama-1",
        "pericope": "OV-Ruth",
        "status": IRSessionStatus.IN_PROGRESS,
        "messages": [],
        "coverage_state": {},
        "kept_takes": {},
        "back_translation": {},
        "language": "pt",
    }
    fields.update(over)
    return IRSession(**fields)


def _warnings(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    return [
        record
        for record in caplog.records
        if record.name == LOGGER_NAME and record.levelno == logging.WARNING
    ]


async def test_a_refused_opening_names_the_session_the_pericope_and_the_reason(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(_panorama())
    await db_session.commit()

    async def _refused(**_: object) -> TurnOutcome:
        return TurnOutcome(
            speech="",
            transcript="",
            used_fail_safe=True,
            draft="Vamos começar pela Familiarização.",
            issues=[{"problem": "imported_knowledge"}],
        )

    monkeypatch.setattr(prepare_opening_module, "run_turn", _refused)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await prepare_opening("panorama-1", pericope="P01")

    warnings = _warnings(caplog)
    assert len(warnings) == 1
    record = warnings[0]
    assert record.__dict__["session_id"] == "panorama-1"
    assert record.__dict__["pericope"] == "P01"
    assert "imported_knowledge" in record.getMessage()


async def test_an_opening_that_fell_on_an_empty_draft_says_the_validator_never_saw_it(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(_panorama())
    await db_session.commit()
    agent = the_agent_answers(monkeypatch, FakeAgent(verdicts=[], drafts=[""]))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await prepare_opening("panorama-1", pericope="P01")

    assert agent.calls == ["guide"]
    (record,) = _warnings(caplog)
    assert record.getMessage() == (
        "Prepared opening fell to the fail-safe on an empty draft for session panorama-1, "
        "pericope P01: the Validator never saw it"
    ), "an empty draft was logged as 'refused by the Validator', which never saw it"
    assert record.__dict__["session_id"] == "panorama-1"
    assert record.__dict__["pericope"] == "P01"


async def test_an_empty_draft_after_a_redraft_does_not_blame_the_issues_that_redraft_left(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(_panorama())
    await db_session.commit()
    agent = the_agent_answers(
        monkeypatch, FakeAgent(verdicts=[REGENERATE], drafts=["Vamos começar.", ""])
    )

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await prepare_opening("panorama-1", pericope="P01")

    assert agent.calls == ["guide", "validator", "guide"]
    (record,) = _warnings(caplog)
    assert record.getMessage() == (
        "Prepared opening fell to the fail-safe on an empty draft for session panorama-1, "
        "pericope P01: the Validator never saw it"
    ), "the first redraft's issues were offered as the reason the empty one fell"
    assert "imported_knowledge" not in str(record.__dict__["reason"])


async def test_an_opening_the_validator_refused_is_still_logged_as_the_validators(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(_panorama())
    await db_session.commit()
    agent = the_agent_answers(monkeypatch, FakeAgent(verdicts=[REGENERATE] * 3))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await prepare_opening("panorama-1", pericope="P01")

    assert agent.calls.count("validator") == 3
    (record,) = _warnings(caplog)
    assert record.getMessage() == (
        "Prepared opening refused by the Validator for session panorama-1, pericope P01: "
        "imported_knowledge"
    ), "a draft the Validator read and turned back stopped being logged as its refusal"


async def test_a_refused_opening_still_leaves_the_session_with_nothing_prepared(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No change to the fallback: a refused draft is discarded, never half-written."""
    db_session.add(_panorama())
    await db_session.commit()

    async def _refused(**_: object) -> TurnOutcome:
        return TurnOutcome(
            speech="",
            transcript="",
            used_fail_safe=True,
            draft="Vamos começar pela Familiarização.",
            issues=[{"problem": "imported_knowledge"}],
        )

    monkeypatch.setattr(prepare_opening_module, "run_turn", _refused)

    await prepare_opening("panorama-1", pericope="P01")

    from app.services.internalization_room.sessions import get_session

    refreshed = await get_session(db_session, "panorama-1")
    assert refreshed.prepared_speech is None
    assert refreshed.prepared_audio_key is None


async def test_a_transport_error_names_the_session_and_the_pericope_not_the_passage(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_session.add(_panorama())
    await db_session.commit()

    async def _spoken(**_: object) -> TurnOutcome:
        return TurnOutcome(speech=PASSAGE_TEXT, transcript="")

    async def _unreachable(*_: object, **__: object) -> None:
        raise RuntimeError("the tts host is unreachable")

    monkeypatch.setattr(prepare_opening_module, "run_turn", _spoken)
    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", _unreachable)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        await prepare_opening("panorama-1", pericope="P01")

    warnings = _warnings(caplog)
    assert len(warnings) == 1
    record = warnings[0]
    assert record.__dict__["session_id"] == "panorama-1"
    assert record.__dict__["pericope"] == "P01"
    assert "the tts host is unreachable" in record.getMessage()
    assert PASSAGE_TEXT not in caplog.text


async def test_a_transport_error_never_raises_out_of_the_background_job(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The optimisation stays optional: a swallowed failure must not become a live crash."""
    db_session.add(_panorama())
    await db_session.commit()

    async def _spoken(**_: object) -> TurnOutcome:
        return TurnOutcome(speech=PASSAGE_TEXT, transcript="")

    async def _unreachable(*_: object, **__: object) -> None:
        raise RuntimeError("the tts host is unreachable")

    monkeypatch.setattr(prepare_opening_module, "run_turn", _spoken)
    monkeypatch.setattr(prepare_opening_module, "synthesize_facilitator_speech", _unreachable)

    await prepare_opening("panorama-1", pericope="P01")
