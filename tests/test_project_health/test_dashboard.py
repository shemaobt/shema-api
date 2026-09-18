from __future__ import annotations

from app.db.models.project_health import PHLanguage
from app.services.project_health import create_interview, list_admin_dashboard


async def test_dashboard_lists_interviews(db_session, ph_app):
    await create_interview(db_session, project_name="A", team_name="T1", language=PHLanguage.EN)
    await create_interview(db_session, project_name="B", team_name="T2", language=PHLanguage.PT)

    interviews, reports = await list_admin_dashboard(db_session)
    assert len(interviews) == 2
    assert reports == []
    names = {i.project_name for i in interviews}
    assert names == {"A", "B"}


async def test_dashboard_empty_when_no_interviews(db_session, ph_app):
    interviews, reports = await list_admin_dashboard(db_session)
    assert interviews == []
    assert reports == []
