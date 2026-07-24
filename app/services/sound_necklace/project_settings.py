import math
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectGranularityLocked
from app.db.models.sound_necklace import GranularityLevel, SnProjectSettings
from app.services.project.get_project_or_404 import get_project_or_404
from app.services.sound_necklace.get_lock_status import as_utc


@dataclass(frozen=True)
class GranularitySettings:
    """A project's bead grid, as the SPA reads it back.

    Both values are nullable and say different things when absent: no ``granularity_level``
    is a project nobody confirmed yet, no ``bead_sec`` is a confirmed project that has not
    cut anything, so no audio has fixed the duration the level resolves to.
    """

    project_id: str
    granularity_level: GranularityLevel | None = None
    bead_sec: float | None = None
    locked: bool = False
    updated_at: datetime | None = None


def _settings(project_id: str, row: SnProjectSettings | None) -> GranularitySettings:
    """Read a settings row out as the API's own shape, so no ORM object leaves the layer.

    ``locked`` is the row existing, not a stored column: the row IS the lock.
    """
    if row is None:
        return GranularitySettings(project_id=project_id)
    return GranularitySettings(
        project_id=project_id,
        granularity_level=row.granularity_level,
        bead_sec=row.bead_sec,
        locked=True,
        updated_at=as_utc(row.updated_at),
    )


async def get_project_settings(db: AsyncSession, project_id: str) -> GranularitySettings:
    """The project's granularity, and whether the level is frozen.

    The row IS the lock: ``granularity_level`` is NOT NULL, so a row existing means an
    admin confirmed a level, and confirming is what freezes it. No session count is
    consulted — a project can be frozen before it has cut anything, which is exactly the
    state the settings screen exists to produce.

    404s an unknown project rather than answering nulls for it: a platform admin is waved
    past ``assert_project_access`` without a project being looked at, so a typo in the id
    would otherwise read back as a perfectly ordinary unconfigured project.
    """
    await get_project_or_404(db, project_id)
    return _settings(project_id, await db.get(SnProjectSettings, project_id))


async def set_project_granularity(
    db: AsyncSession, project_id: str, level: GranularityLevel, updated_by: str
) -> GranularitySettings:
    """Confirm the project's bead granularity — once, permanently.

    Confirming is the freeze. The screen says so on the button ("this does not change
    afterwards"), and the refusal here is what makes that true rather than a warning:
    a level that could move afterwards would either contradict the ``bead_sec`` a session
    already stamped — leaving the project unable to open another session, since every new
    audio would resolve to a grid the stored one rejects — or split the corpus across two
    coordinate systems, which is the thing this row exists to prevent.

    Re-sending the level a project already confirmed is not a change and is allowed
    through, so a double submit or a retry is harmless.

    Takes the project row FOR UPDATE first, which does two jobs: an unknown project is a
    404 rather than a foreign key violation surfacing as a 500, and every writer of this
    table queues behind that one row. The read and the write are separate statements, so
    without it two first callers both find no row and both insert — and the primary key
    turns the loser into a 500 instead of the answer its conflict was owed.
    """
    await get_project_or_404(db, project_id, for_update=True)
    row = await db.get(SnProjectSettings, project_id)
    if row is not None:
        if row.granularity_level == level:
            return _settings(project_id, row)
        raise ProjectGranularityLocked(
            "This project's bead granularity is already confirmed, so the level cannot "
            "change. Re-cutting it means re-deriving every manifest_id already exported."
        )

    row = SnProjectSettings(project_id=project_id, granularity_level=level, updated_by=updated_by)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return _settings(project_id, row)


async def stamp_resolved_bead_sec(
    db: AsyncSession, project_id: str, level: GranularityLevel, bead_sec: float
) -> None:
    """Hold a session to the project's grid, and record that grid when it is the first.

    ``bead_sec`` is ``granularity_frames[level] * hop_sec`` off the audio's own acousteme,
    so nothing knows it before an audio is cut — the admin confirms a level, the first
    session resolves it. From then on it is the value later audios have to agree with, and
    one that does not is refused here rather than trusted. The SPA already declines to cut
    on a second grid, but a stale tab or a client that never ran that check would commit
    the corpus split this table exists to prevent.

    Writes the level too when no row exists. Sessions predate this table, and a project
    grandfathered in that way still needs its grid written down; the level it was cut at
    IS the project's level, and writing it freezes the project exactly as confirming
    would have.

    Called inside ``create_session``'s transaction and does not commit: that call site
    owns the commit that lands the session, its state row and its consent together — and
    owns the rollback that discards them when this refuses one.

    Takes the same project row FOR UPDATE that ``set_project_granularity`` takes, for the
    same reason. The lock lives here rather than in the caller because it is the read
    below that it protects.
    """
    await get_project_or_404(db, project_id, for_update=True)
    row = await db.get(SnProjectSettings, project_id)
    if row is None:
        db.add(SnProjectSettings(project_id=project_id, granularity_level=level, bead_sec=bead_sec))
        return

    if row.granularity_level != level:
        raise ProjectGranularityLocked(
            f"This project is cut at granularity '{row.granularity_level.value}' and this "
            f"session was cut at '{level.value}'. Two grids in one project is the thing "
            "the project setting exists to prevent."
        )
    if row.bead_sec is None:
        row.bead_sec = bead_sec
    elif not math.isclose(row.bead_sec, bead_sec, rel_tol=1e-9):
        raise ProjectGranularityLocked(
            f"This project's bead grid is {row.bead_sec}s and this audio resolves to "
            f"{bead_sec}s. Its acousteme does not agree with the grid the project is "
            "already cut on."
        )
