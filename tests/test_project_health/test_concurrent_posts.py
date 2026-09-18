from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.project_health import PHInterview, PHLanguage
from app.services.project_health import create_interview, post_message


@pytest.mark.skip(
    reason=(
        "Race-condition regression marker for the SELECT FOR UPDATE fix in "
        "post_message. Requires a Postgres test backend to exercise meaningfully; "
        "aiosqlite serializes writes at the file level but does not honour FOR "
        "UPDATE, so the test runs against last-writer-wins semantics and fails "
        "here. Unskip in CI when running against a real Postgres."
    )
)
async def test_concurrent_posts_both_persist(db_session, test_engine, ph_app, stub_llm):
    """Two concurrent POST /messages must both persist their team turn.

    Pre-fix, the JSON-column UPDATE was last-writer-wins and one team turn
    silently disappeared. Post-fix, SELECT ... FOR UPDATE on Postgres
    serializes the writes so both turns persist.
    """
    interview, *_ = await create_interview(
        db_session,
        project_name="Concurrency Test",
        team_name="Test",
        language=PHLanguage.EN,
    )
    interview_id = interview.id
    await db_session.commit()

    session_factory = async_sessionmaker(
        test_engine, expire_on_commit=False, class_=AsyncSession, autoflush=False
    )

    async def post_one(content: str) -> None:
        async with session_factory() as session:
            await post_message(session, interview_id, content)

    await asyncio.gather(
        post_one("First parallel team turn"),
        post_one("Second parallel team turn"),
    )

    async with session_factory() as session:
        refreshed = (
            await session.execute(select(PHInterview).where(PHInterview.id == interview_id))
        ).scalar_one()
        team_messages = [m for m in refreshed.messages if m.get("role") == "team"]
        contents = {m["content"] for m in team_messages}

    assert len(team_messages) == 2, f"Expected 2 team turns, got {team_messages}"
    assert contents == {"First parallel team turn", "Second parallel team turn"}
