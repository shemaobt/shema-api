from __future__ import annotations

from typing import Any

import pytest

from app.db.models.project_health import PHLanguage
from app.services.project_health import create_interview, post_message
from app.services.project_health.agents import orchestrator


@pytest.mark.asyncio
async def test_post_message_handles_malformed_llm_json(db_session, ph_app, monkeypatch):
    """When Gemini returns invalid JSON, safe_parse_json falls back to the
    default and the interview should still progress (facilitator reply,
    coverage state retained) rather than crashing."""
    interview, *_ = await create_interview(
        db_session,
        project_name="Malformed LLM",
        team_name="Test",
        language=PHLanguage.EN,
    )

    async def malformed_call_agent(
        *,
        system_prompt: str,
        user_content: str,
        model: str | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
        expects_json: bool = False,
        settings: Any | None = None,
    ) -> str:
        return "this is not valid json at all { broken"

    async def stable_call_chat(
        *,
        system_prompt: str,
        contents: list[dict],
        model: str | None = None,
        temperature: float = 0.6,
        max_output_tokens: int = 500,
        settings: Any | None = None,
    ) -> str:
        return "Tell me more about your team."

    monkeypatch.setattr(orchestrator, "call_agent", malformed_call_agent)
    monkeypatch.setattr(orchestrator, "call_chat", stable_call_chat)

    facilitator_msg, coverage = await post_message(
        db_session, interview.id, "Hello, we're the test team."
    )

    assert facilitator_msg.role == "facilitator"
    assert facilitator_msg.content == "Tell me more about your team."
    assert coverage.interview_phase in {"opening", "exploring", "deepening", "closing"}
