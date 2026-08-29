from __future__ import annotations

import json
from typing import Any

import pytest

from app.db.models.project_health import PHLanguage
from app.services.project_health.agents import orchestrator
from tests.baker import make_app, make_role

_ALL_DOMAINS = (
    "local_leadership",
    "capacity_training",
    "church_community",
    "resources_infrastructure",
    "strategic_planning",
    "collaboration",
    "pace_trajectory",
)
_ALL_OPENING_FIELDS = (
    "respondent_name",
    "participants_present",
    "language_name",
    "language_code_or_unknown",
    "team_size",
    "team_roles",
)


@pytest.fixture()
async def ph_app(db_session):
    app = await make_app(db_session, app_key="project-health", name="Project Health")
    await make_role(db_session, app.id, role_key="user", label="User", is_system=True)
    await make_role(db_session, app.id, role_key="admin", label="Admin", is_system=True)
    return app


@pytest.fixture()
def stub_llm(monkeypatch):
    """Replace every LLM call with deterministic stubs so tests don't hit the
    Gemini API. Each stub returns a JSON-encoded string when the calling agent
    expects JSON, or a plain string when it doesn't."""

    async def fake_call_agent(
        *,
        system_prompt: str,
        user_content: str,
        model: str | None = None,
        temperature: float = 0.4,
        max_output_tokens: int = 2000,
        expects_json: bool = False,
        settings: Any | None = None,
    ) -> str:
        prompt = system_prompt or ""
        if "Coverage Planner" in prompt:
            return json.dumps(
                {
                    "domains_touched": dict.fromkeys(_ALL_DOMAINS, 2),
                    "domains_with_evidence": list(_ALL_DOMAINS),
                    "suggested_next_domain": None,
                    "interview_phase": "closing",
                    "turn_count": 10,
                    "opening_fields": dict.fromkeys(_ALL_OPENING_FIELDS, True),
                    "missing_opening_fields": [],
                    "coverage_hint": "All covered.",
                }
            )
        if "Evidence Mapper" in prompt:
            return json.dumps(
                [
                    {
                        "domain": "local_leadership",
                        "quote_summary": "Local leaders are present.",
                        "sentiment": "positive",
                        "turn_index": 0,
                    }
                ]
            )
        if "Scoring agent" in prompt:
            return json.dumps(
                [
                    {
                        "domain": d,
                        "score": 4,
                        "confidence": 3,
                        "rationale": "stub",
                        "risks": [],
                        "strengths": [],
                        "evidence_refs": [],
                    }
                    for d in _ALL_DOMAINS
                ]
            )
        if "Guardrail agent" in prompt:
            return json.dumps({"approved": True, "violations": [], "suggested_fix": ""})
        if "extract interview context" in prompt:
            return json.dumps(
                {
                    "respondent_name": "Test",
                    "participants_present": ["Test"],
                    "language_name": "English",
                    "language_code": "en",
                    "team_size": "5",
                    "team_roles": ["Test - lead"],
                }
            )
        if "team-facing project health report" in prompt:
            return json.dumps(
                {
                    "summary": "summary",
                    "strengths": ["s1"],
                    "growth_areas": ["g1"],
                    "next_steps": ["n1"],
                    "closing": "closing",
                }
            )
        if "admin-facing OBT project health report" in prompt:
            return json.dumps(
                {
                    "overall_sustainability_index": 4,
                    "top_risks": ["r1"],
                    "recommended_actions": ["a1"],
                    "interview_quality": {
                        "coverage_breadth": 4,
                        "evidence_depth": 4,
                        "confidence_avg": 4,
                    },
                }
            )
        return ""

    async def fake_call_chat(
        *,
        system_prompt: str,
        contents: list[dict],
        model: str | None = None,
        temperature: float = 0.6,
        max_output_tokens: int = 500,
        settings: Any | None = None,
    ) -> str:
        return "Tell me more about your team."

    monkeypatch.setattr(orchestrator, "call_agent", fake_call_agent)
    monkeypatch.setattr(orchestrator, "call_chat", fake_call_chat)


@pytest.fixture()
def language_en() -> PHLanguage:
    return PHLanguage.EN
