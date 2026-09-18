from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.project_health import PHLanguage, PHReport
from app.services.project_health import complete_interview, create_interview

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


@pytest.mark.skip(
    reason=(
        "Idempotency regression marker for the IntegrityError-catch fix in "
        "complete_interview. Requires a Postgres test backend; aiosqlite does "
        "not support concurrent async sessions cleanly (greenlet issues). "
        "Unskip in CI when running against a real Postgres."
    )
)
async def test_concurrent_complete_returns_same_report(db_session, test_engine, ph_app, stub_llm):
    """Two concurrent POST /complete on the same interview must both return
    the same report_id (idempotent), and exactly one PHReport row exists."""
    interview, *_ = await create_interview(
        db_session,
        project_name="Concurrent Complete",
        team_name="Test",
        language=PHLanguage.EN,
    )
    interview.coverage_state = {
        "opening_fields": dict.fromkeys(_ALL_OPENING_FIELDS, True),
        "missing_opening_fields": [],
        "domains_with_evidence": list(_ALL_DOMAINS),
    }
    interview.messages = [
        *interview.messages,
        *[
            {"role": "team", "content": f"t{i}", "timestamp": "2026-01-01T00:00:00Z"}
            for i in range(10)
        ],
    ]
    interview_id = interview.id
    await db_session.commit()

    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
    )

    async def finish() -> str:
        async with session_factory() as session:
            report_id, _ = await complete_interview(session, interview_id)
            return report_id

    first, second = await asyncio.gather(finish(), finish())
    assert first == second

    async with session_factory() as session:
        reports = (
            (await session.execute(select(PHReport).where(PHReport.interview_id == interview_id)))
            .scalars()
            .all()
        )
        assert len(reports) == 1
