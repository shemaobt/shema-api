"""The hours' recordings measured on their own file, and the stored durations that disagree."""

from collections import defaultdict
from dataclasses import dataclass

from google.api_core.exceptions import NotFound
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.oc_recording import OC_Recording
from app.services.oral_collector import gcs_utils
from app.services.oral_collector.constants import gcs_oc_bucket
from app.services.oral_collector.stats_service import counted_recording_conditions
from app.services.platform.audio_duration import measure_ms

TOLERANCE_SECONDS = 1.0


@dataclass(frozen=True)
class Divergent:
    recording_id: str
    project_id: str
    stored_seconds: float
    measured_seconds: float


@dataclass(frozen=True)
class Unreadable:
    recording_id: str
    project_id: str
    reason: str


@dataclass(frozen=True)
class ProjectHours:
    project_id: str
    before: float
    after: float


@dataclass(frozen=True)
class DurationAudit:
    bucket: str
    divergent: list[Divergent]
    unreadable: list[Unreadable]
    hours: list[ProjectHours]
    written: int


async def audit_durations(
    sessions: async_sessionmaker[AsyncSession], *, write: bool
) -> DurationAudit:
    bucket = gcs_oc_bucket()
    async with sessions() as db:
        counted = (
            await db.execute(
                select(
                    OC_Recording.id,
                    OC_Recording.project_id,
                    OC_Recording.duration_seconds,
                    OC_Recording.gcs_url,
                )
                .where(*counted_recording_conditions())
                .order_by(OC_Recording.id)
            )
        ).all()

    stored_seconds: dict[str, float] = defaultdict(float)
    divergent: list[Divergent] = []
    unreadable: list[Unreadable] = []
    for recording in counted:
        stored = recording.duration_seconds or 0.0
        stored_seconds[recording.project_id] += stored
        measured = await _measured_seconds(bucket, recording.gcs_url)
        if isinstance(measured, str):
            unreadable.append(Unreadable(recording.id, recording.project_id, measured))
        elif abs(measured - stored) > TOLERANCE_SECONDS:
            divergent.append(Divergent(recording.id, recording.project_id, stored, measured))

    if write and divergent:
        async with sessions.begin() as db:
            for row in divergent:
                await db.execute(
                    update(OC_Recording)
                    .where(OC_Recording.id == row.recording_id)
                    .values(duration_seconds=row.measured_seconds)
                )

    return DurationAudit(
        bucket=bucket,
        divergent=divergent,
        unreadable=unreadable,
        hours=_hours_of_touched_projects(stored_seconds, divergent),
        written=len(divergent) if write else 0,
    )


async def _measured_seconds(bucket: str, gcs_url: str | None) -> float | str:
    blob_name = gcs_utils.blob_name_from_url(gcs_url) if gcs_url else None
    if blob_name is None:
        return "no file address"
    try:
        audio = await gcs_utils.download_gcs_object(bucket, blob_name)
    except NotFound:
        return "file not found"
    ms = await measure_ms(audio)
    if ms is None:
        return "ffprobe could not read the file"
    return ms / 1000


def _hours_of_touched_projects(
    stored_seconds: dict[str, float], divergent: list[Divergent]
) -> list[ProjectHours]:
    change: dict[str, float] = defaultdict(float)
    for row in divergent:
        change[row.project_id] += row.measured_seconds - row.stored_seconds
    return [
        ProjectHours(
            project_id,
            round(stored_seconds[project_id] / 3600, 2),
            round((stored_seconds[project_id] + delta) / 3600, 2),
        )
        for project_id, delta in change.items()
    ]
