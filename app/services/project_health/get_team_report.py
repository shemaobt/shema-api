from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.project_health import PHInterview, PHReport
from app.models.project_health import TeamReport, TeamReportResponse


async def get_team_report(db: AsyncSession, report_id: str) -> TeamReportResponse:
    """Return the team-facing report subset; raises NotFoundError when missing."""
    report_stmt = select(PHReport).where(PHReport.id == report_id)
    report_row = (await db.execute(report_stmt)).scalar_one_or_none()
    if report_row is None:
        raise NotFoundError("Report not found")

    interview_stmt = select(PHInterview).where(PHInterview.id == report_row.interview_id)
    interview_row = (await db.execute(interview_stmt)).scalar_one_or_none()
    if interview_row is None:
        raise NotFoundError("Interview not found")

    return TeamReportResponse(
        id=report_row.id,
        interview_id=report_row.interview_id,
        project_name=interview_row.project_name,
        team_name=interview_row.team_name,
        language=interview_row.language,
        team_report=TeamReport.model_validate(report_row.team_report),
        created_at=report_row.created_at,
    )
