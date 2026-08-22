import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.phase import Phase, PhaseStatus, ProjectPhase


async def attach_all_phases_to_project(db: AsyncSession, project_id: str) -> None:
    phase_ids = (await db.execute(select(Phase.id))).scalars().all()
    linked = (
        (
            await db.execute(
                select(ProjectPhase.phase_id).where(ProjectPhase.project_id == project_id)
            )
        )
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
        for phase_id in set(phase_ids) - set(linked)
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
