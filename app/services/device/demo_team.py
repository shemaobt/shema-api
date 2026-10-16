"""The demo team (ADR 0064): the team the demo page spends codes on, marked on its own row.

The setting names the team and opens the page. The mark is what the rules read, so a demo
team's devices keep them after the setting is unset.
"""

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.project import Project

logger = logging.getLogger(__name__)


async def is_the_demo_team(db: AsyncSession, project_id: str | None) -> bool:
    if project_id is None:
        return False
    marked = await db.scalar(select(Project.is_demo_team).where(Project.id == project_id))
    return bool(marked)


async def the_demo_team(db: AsyncSession) -> str | None:
    """The configured team, marked as the demo team for good, or None with no team to serve."""
    configured = get_settings().internalization_room_demo_team_id
    if not configured:
        return None
    project = await db.get(Project, configured)
    if project is None:
        logger.warning("demo team not found", extra={"demo_team_id": configured})
        return None
    if not project.is_demo_team:
        project.is_demo_team = True
        await db.commit()
    return configured
