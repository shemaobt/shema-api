from __future__ import annotations

import pytest

from app.core.auth_middleware import require_platform_admin
from app.core.exceptions import AuthorizationError, NotFoundError
from app.db.models.project_health import PHInterview, PHLanguage, PHReport
from app.services.project_health import (
    create_interview,
    delete_interview,
    get_admin_interview_detail,
)
from tests.baker import make_user


async def test_get_admin_interview_detail_returns_full_row(db_session, ph_app, stub_llm):
    interview, _token, _exp, _msg, _cov = await create_interview(
        db_session, project_name="A", team_name="T", language=PHLanguage.EN
    )

    fetched = await get_admin_interview_detail(db_session, interview.id)

    assert fetched.id == interview.id
    assert fetched.project_name == "A"
    assert fetched.team_name == "T"
    assert isinstance(fetched.messages, list)


async def test_get_admin_interview_detail_404_for_unknown(db_session, ph_app):
    with pytest.raises(NotFoundError):
        await get_admin_interview_detail(db_session, "00000000-0000-0000-0000-000000000000")


async def test_delete_interview_removes_row_and_cascades_report(db_session, ph_app, stub_llm):
    interview, _token, _exp, _msg, _cov = await create_interview(
        db_session, project_name="A", team_name="T", language=PHLanguage.EN
    )
    db_session.add(
        PHReport(
            interview_id=interview.id,
            team_report={"summary": "x"},
            admin_report={
                "overall_sustainability_index": 0,
                "domain_scores": [],
                "interview_quality": {
                    "coverage_breadth": 0,
                    "evidence_depth": 0,
                    "confidence_avg": 0,
                },
            },
        )
    )
    await db_session.commit()
    interview_id = interview.id

    await delete_interview(db_session, interview_id)

    assert await db_session.get(PHInterview, interview_id) is None
    assert await db_session.get(PHReport, interview_id) is None


async def test_delete_interview_404_for_unknown(db_session, ph_app):
    with pytest.raises(NotFoundError):
        await delete_interview(db_session, "00000000-0000-0000-0000-000000000000")


async def test_require_platform_admin_rejects_non_platform_admin(db_session):
    user = await make_user(db_session, email="ph_admin@example.com", is_platform_admin=False)
    with pytest.raises(AuthorizationError):
        await require_platform_admin(user=user)


async def test_require_platform_admin_allows_platform_admin(db_session):
    admin = await make_user(db_session, email="platform@example.com", is_platform_admin=True)
    result = await require_platform_admin(user=admin)
    assert result.id == admin.id
