"""The agent layer must ask for JSON, and must say so when it is cut off.

Both guards come from the first real interview ever run through this service. It logged
nineteen JSON parse failures, several holding nothing but a single `{`, and every one of
them degraded silently to a fallback — an empty interview context, no evidence, an
approving guardrail. The delivered report looked fine; its header was blank.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from google.genai import types

from app.core.config import Settings
from app.services.project_health.agents import llm_client


def _settings() -> Settings:
    return Settings(database_url="sqlite+aiosqlite:///./test.db", google_api_key="fake-google")


def _response(text: str, finish: types.FinishReason = types.FinishReason.STOP) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        candidates=[SimpleNamespace(finish_reason=finish)],
        usage_metadata=SimpleNamespace(candidates_token_count=1, thoughts_token_count=880),
    )


def _client(response: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        aio=SimpleNamespace(
            models=SimpleNamespace(generate_content=AsyncMock(return_value=response))
        )
    )


@pytest.mark.asyncio
async def test_a_caller_that_parses_json_asks_the_model_for_json() -> None:
    """Without JSON mode the model may fence or preface the object, and the parse falls back."""
    client = _client(_response('{"respondent_name": "Maria"}'))
    with patch.object(llm_client.genai, "Client", return_value=client):
        await llm_client.call_agent(
            system_prompt="p",
            user_content="c",
            expects_json=True,
            max_output_tokens=2000,
            settings=_settings(),
        )

    config = client.aio.models.generate_content.await_args.kwargs["config"]
    assert config.response_mime_type == "application/json"


@pytest.mark.asyncio
async def test_a_prose_caller_is_left_in_prose_mode() -> None:
    """The facilitator's reply is spoken to a person; JSON mode would ruin it."""
    client = _client(_response("It is nice to meet you, Maria."))
    with patch.object(llm_client.genai, "Client", return_value=client):
        await llm_client.call_agent(system_prompt="p", user_content="c", settings=_settings())

    config = client.aio.models.generate_content.await_args.kwargs["config"]
    assert config.response_mime_type is None


@pytest.mark.asyncio
async def test_a_truncated_answer_is_reported(caplog: pytest.LogCaptureFixture) -> None:
    """The stub still returns — the caller has a fallback — but it stops being invisible.

    The logged thinking count is the number that explains the truncation: it is spent from
    the same budget as the answer, so a cap that reads as generous can leave almost none.
    """
    client = _client(_response("{", finish=types.FinishReason.MAX_TOKENS))
    with caplog.at_level("WARNING"), patch.object(llm_client.genai, "Client", return_value=client):
        text = await llm_client.call_agent(
            system_prompt="p",
            user_content="c",
            expects_json=True,
            max_output_tokens=900,
            settings=_settings(),
        )

    assert text == "{"
    assert "truncated" in caplog.text
    assert "thinking_tokens=880" in caplog.text


@pytest.mark.asyncio
async def test_a_complete_answer_is_not_reported(caplog: pytest.LogCaptureFixture) -> None:
    client = _client(_response('{"ok": true}'))
    with caplog.at_level("WARNING"), patch.object(llm_client.genai, "Client", return_value=client):
        await llm_client.call_agent(
            system_prompt="p", user_content="c", expects_json=True, settings=_settings()
        )

    assert "truncated" not in caplog.text


@pytest.mark.asyncio
async def test_the_team_report_names_the_team_it_is_addressed_to(db_session, ph_app) -> None:
    """Project and team come from what the team typed, never from an extraction.

    The report page had nothing else to read them from and hardcoded empty strings, so
    every report rendered "For the —, with appreciation" above a body that named the team
    correctly in prose.
    """
    from app.db.models.project_health import PHInterview, PHReport
    from app.services.project_health.get_team_report import get_team_report

    interview = PHInterview(
        project_name="Terena OBT",
        team_name="Terena Storytellers",
        language="en",
        status="completed",
        messages=[],
        coverage_state={},
        evidence=[],
    )
    db_session.add(interview)
    await db_session.commit()
    await db_session.refresh(interview)
    report = PHReport(
        interview_id=interview.id,
        team_report={
            "summary": "s",
            "strengths": [],
            "growth_areas": [],
            "next_steps": [],
            "closing": "c",
        },
        admin_report={},
    )
    db_session.add(report)
    await db_session.commit()
    await db_session.refresh(report)

    response = await get_team_report(db_session, report.id)

    assert response.project_name == "Terena OBT"
    assert response.team_name == "Terena Storytellers"
