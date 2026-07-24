from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ProjectGranularityLocked
from app.db.models.sound_necklace import GranularityLevel, SnProjectSettings


async def get_project_settings(
    db: AsyncSession, project_id: str
) -> tuple[SnProjectSettings | None, bool]:
    """The project's granularity row (or None), and whether the level is frozen.

    The row IS the lock: ``granularity_level`` is NOT NULL, so a row existing means an
    admin confirmed a level, and confirming is what freezes it. No session count is
    consulted — a project can be frozen before it has cut anything, which is exactly the
    state the settings screen exists to produce.
    """
    row = await db.get(SnProjectSettings, project_id)
    return row, row is not None


async def set_project_granularity(
    db: AsyncSession, project_id: str, level: GranularityLevel, updated_by: str
) -> tuple[SnProjectSettings, bool]:
    """Confirm the project's bead granularity — once, permanently.

    Confirming is the freeze. The screen says so on the button ("this does not change
    afterwards"), and the refusal here is what makes that true rather than a warning:
    a level that could move afterwards would either contradict the ``bead_sec`` a session
    already stamped — leaving the project unable to open another session, since every new
    audio would resolve to a grid the stored one rejects — or split the corpus across two
    coordinate systems, which is the thing this row exists to prevent.

    Re-sending the level a project already confirmed is not a change and is allowed
    through, so a double submit or a retry is harmless.
    """
    row = await db.get(SnProjectSettings, project_id)
    if row is not None:
        if row.granularity_level == level:
            return row, True
        raise ProjectGranularityLocked(
            "This project's bead granularity is already confirmed, so the level cannot "
            "change. Re-cutting it means re-deriving every manifest_id already exported."
        )

    row = SnProjectSettings(project_id=project_id, granularity_level=level, updated_by=updated_by)
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row, True


async def stamp_resolved_bead_sec(
    db: AsyncSession, project_id: str, level: GranularityLevel, bead_sec: float
) -> None:
    """Record the grid the project's first session landed on.

    ``bead_sec`` is ``granularity_frames[level] * hop_sec`` off the audio's own acousteme,
    so nothing knows it before an audio is cut — the admin confirms a level, the first
    session resolves it. From then on it is the value later audios have to agree with,
    and the SPA refuses one whose acousteme would resolve differently.

    Writes the level too when no row exists. Sessions predate this table, and a project
    grandfathered in that way still needs its grid written down; the level it was cut at
    IS the project's level, and writing it freezes the project exactly as confirming
    would have. It never overwrites a level already confirmed — a session disagreeing
    with its project would be a bug to surface, not to enshrine.

    Called inside ``create_session``'s transaction and does not commit: that call site
    owns the commit that lands the session, its state row and its consent together.
    """
    row = await db.get(SnProjectSettings, project_id)
    if row is None:
        row = SnProjectSettings(project_id=project_id, granularity_level=level)
        db.add(row)
    if row.bead_sec is None:
        row.bead_sec = bead_sec
