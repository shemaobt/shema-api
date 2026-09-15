import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import PhaseStatus, ProjectPhase
from app.db.models.project import Project


async def attach_phase_to_all_projects(db: AsyncSession, phase_id: str) -> None:
    project_ids = (await db.execute(select(Project.id))).scalars().all()
    linked = (
        (await db.execute(select(ProjectPhase.project_id).where(ProjectPhase.phase_id == phase_id)))
        .scalars()
        .all()
    )
    rows = [
        {
            "id": str(uuid.uuid4()),
            "project_id": project_id,
            "phase_id": phase_id,
            "status": PhaseStatus.NOT_STARTED,
        }
        for project_id in set(project_ids) - set(linked)
    ]
    if not rows:
        return
    insert = pg_insert if db.bind.dialect.name == "postgresql" else sqlite_insert
    await db.execute(
        insert(ProjectPhase)
        .values(rows)
        .on_conflict_do_nothing(index_elements=["project_id", "phase_id"])
    )
    await db.flush()
