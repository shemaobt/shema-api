from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.db.models.project_health import PHInterview, PHReport
from app.models.project_health import (
    AdminReport,
    AdminReportResponse,
    TeamReport,
)

logger = logging.getLogger(__name__)


async def get_admin_report(
    db: AsyncSession, report_id: str, *, actor_user_id: str | None = None
) -> AdminReportResponse:
    """Return the full team + admin report payload for admin consumers.

    Emits an audit log line keyed by actor + report so admin reads of
    sensitive content (per-team risk assessments, leadership scoring) are
    traceable. `actor_user_id` is optional only to keep tests simple; the
    router always passes it.
    """
    report_stmt = select(PHReport).where(PHReport.id == report_id)
    report_row = (await db.execute(report_stmt)).scalar_one_or_none()
    if report_row is None:
        raise NotFoundError("Report not found")

    interview_stmt = select(PHInterview).where(PHInterview.id == report_row.interview_id)
    interview_row = (await db.execute(interview_stmt)).scalar_one_or_none()
    if interview_row is None:
        raise NotFoundError("Interview not found")

    logger.info(
        "project_health.get_admin_report",
        extra={
            "ph_event": "ph_admin_report_viewed",
            "actor_user_id": actor_user_id,
            "report_id": report_row.id,
            "interview_id": report_row.interview_id,
        },
    )

    return AdminReportResponse(
        id=report_row.id,
        interview_id=report_row.interview_id,
        language=interview_row.language,
        team_report=TeamReport.model_validate(report_row.team_report),
        admin_report=AdminReport.model_validate(report_row.admin_report),
        created_at=report_row.created_at,
    )
