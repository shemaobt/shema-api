from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.exceptions import AuthenticationError, ConflictError
from app.db.models.project_health import PHInterview, PHInterviewStatus, PHReport
from app.services.project_health import (
    MIN_TEAM_TURNS,
    complete_interview,
    create_interview,
    decode_interview_token,
    post_message,
)
from app.services.project_health.complete_interview import InterviewIncompleteError


async def test_create_interview_returns_token_and_first_message(db_session, ph_app, language_en):
    interview, token, expires_at, first_message, coverage = await create_interview(
        db_session,
        project_name="Andean OBT",
        team_name="Quechua",
        language=language_en,
    )

    assert interview.id
    assert interview.status == PHInterviewStatus.IN_PROGRESS
    assert first_message.role == "facilitator"
    assert "name" in first_message.content.lower()
    assert coverage.interview_phase == "opening"
    assert "respondent_name" in coverage.missing_opening_fields
    assert expires_at > datetime.now(UTC)

    claims = decode_interview_token(token)
    assert claims.interview_id == interview.id


async def test_decode_rejects_invalid_token(db_session, ph_app):
    with pytest.raises(AuthenticationError):
        decode_interview_token("not-a-real-token")


async def test_post_message_appends_turns(db_session, ph_app, language_en, stub_llm):
    interview, _, _, _, _ = await create_interview(
        db_session,
        project_name="Andean OBT",
        team_name="Quechua",
        language=language_en,
    )

    facilitator_msg, _coverage = await post_message(
        db_session, interview.id, "I am Mariana, leading the work."
    )

    assert facilitator_msg.role == "facilitator"
    assert facilitator_msg.content
    refreshed = (
        await db_session.execute(select(PHInterview).where(PHInterview.id == interview.id))
    ).scalar_one()
    roles = [m["role"] for m in refreshed.messages]
    assert roles == ["facilitator", "team", "facilitator"]


async def test_post_message_rejects_completed_interview(db_session, ph_app, language_en):
    interview, _, _, _, _ = await create_interview(
        db_session,
        project_name="X",
        team_name="Y",
        language=language_en,
    )
    interview.status = PHInterviewStatus.COMPLETED
    await db_session.commit()

    with pytest.raises(ConflictError):
        await post_message(db_session, interview.id, "hello")


async def test_complete_blocked_when_coverage_incomplete(db_session, ph_app, language_en):
    interview, _, _, _, _ = await create_interview(
        db_session,
        project_name="X",
        team_name="Y",
        language=language_en,
    )

    with pytest.raises(InterviewIncompleteError) as exc_info:
        await complete_interview(db_session, interview.id)

    payload = exc_info.value.payload
    assert payload.completion_ready is False
    assert payload.minimum_team_turns == MIN_TEAM_TURNS
    assert "respondent_name" in payload.missing_opening_fields
    assert "local_leadership" in payload.missing_domains


async def test_complete_writes_report_and_flips_status(db_session, ph_app, language_en, stub_llm):
    interview, _, _, _, _ = await create_interview(
        db_session,
        project_name="X",
        team_name="Y",
        language=language_en,
    )
    interview.coverage_state = {
        "domains_touched": {},
        "domains_with_evidence": [
            "local_leadership",
            "capacity_training",
            "church_community",
            "resources_infrastructure",
            "strategic_planning",
            "collaboration",
            "pace_trajectory",
        ],
        "suggested_next_domain": None,
        "interview_phase": "closing",
        "turn_count": 10,
        "opening_fields": {
            "respondent_name": True,
            "participants_present": True,
            "language_name": True,
            "language_code_or_unknown": True,
            "team_size": True,
            "team_roles": True,
        },
        "missing_opening_fields": [],
    }
    interview.messages = [
        *interview.messages,
        *[
            {"role": "team", "content": f"team {i}", "timestamp": "2026-01-01T00:00:00Z"}
            for i in range(10)
        ],
    ]
    await db_session.commit()

    report_id, team_report = await complete_interview(db_session, interview.id)

    assert report_id
    assert team_report.summary == "summary"
    refreshed = (
        await db_session.execute(select(PHInterview).where(PHInterview.id == interview.id))
    ).scalar_one()
    assert refreshed.status == PHInterviewStatus.COMPLETED
    assert refreshed.completed_at is not None

    report = (
        await db_session.execute(select(PHReport).where(PHReport.interview_id == interview.id))
    ).scalar_one()
    assert report.id == report_id


async def test_complete_idempotent_when_report_exists(db_session, ph_app, language_en, stub_llm):
    interview, _, _, _, _ = await create_interview(
        db_session,
        project_name="X",
        team_name="Y",
        language=language_en,
    )
    interview.coverage_state = {
        "opening_fields": dict.fromkeys(
            (
                "respondent_name",
                "participants_present",
                "language_name",
                "language_code_or_unknown",
                "team_size",
                "team_roles",
            ),
            True,
        ),
        "missing_opening_fields": [],
        "domains_with_evidence": [
            "local_leadership",
            "capacity_training",
            "church_community",
            "resources_infrastructure",
            "strategic_planning",
            "collaboration",
            "pace_trajectory",
        ],
    }
    interview.messages = [
        *interview.messages,
        *[
            {"role": "team", "content": f"t{i}", "timestamp": "2026-01-01T00:00:00Z"}
            for i in range(10)
        ],
    ]
    await db_session.commit()

    first_id, _ = await complete_interview(db_session, interview.id)
    second_id, _ = await complete_interview(db_session, interview.id)
    assert first_id == second_id
