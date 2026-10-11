"""ENG-1567 — a team the harness builds never takes a language code another team holds."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from tests.baker import a_language
from tests.release_harness import a_claimed_device


async def test_two_teams_whose_facilitators_share_an_email_prefix_each_have_their_own_language(
    db_session: AsyncSession,
) -> None:
    first, _ = await a_claimed_device(db_session, email="fac1@example.com")
    second, _ = await a_claimed_device(db_session, email="fac2@example.com")

    codes = (await db_session.execute(select(Language.code))).scalars().all()
    assert first.id != second.id
    assert first.language_id != second.language_id
    assert len(codes) == len(set(codes)) == 2


async def test_a_language_built_with_an_explicit_code_keeps_that_code(
    db_session: AsyncSession,
) -> None:
    language = await a_language(db_session, code="xyz")

    assert language.code == "xyz"
