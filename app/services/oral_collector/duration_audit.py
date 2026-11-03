"""The hours' recordings measured on their own file, and the stored durations that disagree."""

import asyncio
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
MEASURE_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class Divergent:
    recording_id: str
    project_id: str
    stored_seconds: float
    measured_seconds: float
    gcs_url: str
    stored_as_read: float | None


@dataclass(frozen=True)
class Unreadable:
    recording_id: str
    project_id: str
    reason: str


@dataclass(frozen=True)
class Measurement:
    seconds: float | None
    reason: str = ""


@dataclass(frozen=True)
class ProjectHours:
    project_id: str
    before: float
    after: float


@dataclass(frozen=True)
class DurationAudit:
    divergent: list[Divergent]
    unreadable: list[Unreadable]
    hours: list[ProjectHours]
    changed_during_the_run: list[Divergent]
    written: int


async def audit_durations(
    sessions: async_sessionmaker[AsyncSession], *, write: bool
) -> DurationAudit:
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

    stored_seconds_by_project: dict[str, float] = defaultdict(float)
    divergent: list[Divergent] = []
    unreadable: list[Unreadable] = []
    for recording in counted:
        stored = recording.duration_seconds or 0.0
        stored_seconds_by_project[recording.project_id] += stored
        measurement = await _measure(gcs_oc_bucket(), recording.gcs_url)
        if measurement.seconds is None:
            unreadable.append(Unreadable(recording.id, recording.project_id, measurement.reason))
        elif abs(measurement.seconds - stored) > TOLERANCE_SECONDS:
            divergent.append(
                Divergent(
                    recording.id,
                    recording.project_id,
                    stored,
                    measurement.seconds,
                    recording.gcs_url,
                    recording.duration_seconds,
                )
            )

    written: list[Divergent] = []
    changed: list[Divergent] = []
    if write and divergent:
        async with sessions.begin() as db:
            for row in divergent:
                result = await db.execute(
                    update(OC_Recording)
                    .where(
                        OC_Recording.id == row.recording_id,
                        OC_Recording.gcs_url == row.gcs_url,
                        OC_Recording.duration_seconds.is_not_distinct_from(row.stored_as_read),
                        *counted_recording_conditions(),
                    )
                    .values(duration_seconds=row.measured_seconds)
                )
                (written if result.rowcount == 1 else changed).append(row)

    return DurationAudit(
        divergent=divergent,
        unreadable=unreadable,
        hours=_hours_of_touched_projects(
            stored_seconds_by_project, [row for row in divergent if row not in changed]
        ),
        changed_during_the_run=changed,
        written=len(written),
    )


async def _measure(bucket: str, gcs_url: str | None) -> Measurement:
    blob_name = gcs_utils.blob_name_from_url(gcs_url) if gcs_url else None
    if blob_name is None:
        return Measurement(None, "no file address")
    try:
        audio = await gcs_utils.download_gcs_object(bucket, blob_name)
    except NotFound:
        return Measurement(None, "file not found")
    except Exception as error:
        return Measurement(None, f"could not read the file: {type(error).__name__}: {error}")
    try:
        ms = await asyncio.wait_for(measure_ms(audio), MEASURE_TIMEOUT_SECONDS)
    except TimeoutError:
        return Measurement(None, f"measurement timed out after {MEASURE_TIMEOUT_SECONDS:g} s")
    if ms is None:
        return Measurement(None, "ffprobe could not read the file")
    if ms <= 0:
        return Measurement(None, "file has no audio length")
    return Measurement(ms / 1000)


def _hours_of_touched_projects(
    stored_seconds_by_project: dict[str, float], divergent: list[Divergent]
) -> list[ProjectHours]:
    change: dict[str, float] = defaultdict(float)
    for row in divergent:
        change[row.project_id] += row.measured_seconds - row.stored_seconds
    return [
        ProjectHours(
            project_id,
            round(stored_seconds_by_project[project_id] / 3600, 2),
            round((stored_seconds_by_project[project_id] + delta) / 3600, 2),
        )
        for project_id, delta in change.items()
    ]
